"""A fábrica do modelo dos quatro agentes. Um lugar só.

ADR-0017. Os quatro agentes usam o **mesmo** modelo, e o nome mora em
`app/config.py`. Este módulo existe porque passar o nome como string ao
`LlmAgent` **não funciona neste projeto**, por duas razões que só aparecem em
execução:

**1. A chave não chega.** Com `model="gemini-3.5-flash-lite"`, o ADK constrói o
cliente internamente e lê `GOOGLE_API_KEY` do `os.environ` — e o `.env` deste
projeto **não** é copiado para lá. O resultado é
`ValueError: No API key was provided`, com a chave sentada no arquivo. É o
**mesmo bug** que o ADR-0020 registrou para os embeddings, aparecendo pela
segunda vez noutro lugar: ninguém lê o `.env` por nós.

**2. `retry_options` não existe em string.** A decisão `modelos/D-02`
(ADR-0018) precisa de `HttpRetryOptions` no modelo, e esse campo é do objeto
`Gemini`, não da string.

Construir o objeto resolve os dois de uma vez, e deixa a autenticação
explícita em vez de ambiente implícito.
"""

from __future__ import annotations

from google.adk.models.google_llm import Gemini
from google.genai import types

from app.config import MODELO, MODELOS_CONHECIDOS, obter_configuracao
from app.infra.embeddings import ChaveDeApiAusente, MENSAGEM_SEM_CHAVE

TEMPO_LIMITE_MS = 60_000
"""Teto de 60 s por requisição ao modelo. **Sem isto, o `retry_options` é
inútil contra o modo de falha mais comum.**

Medido nesta sessão, e foi o que explicou uma suíte que "nunca terminava": o
processo ficou **4min26 com 13 segundos de CPU** — 97% parado — e **12
conexões ao Google abertas e penduradas**. Nenhuma delas deu erro: ficaram
esperando resposta.

E é aí que está o ponto: `HttpRetryOptions` reage a **erro**. Socket pendurado
não é erro, é silêncio — então a retentativa nunca dispara e o turno espera
para sempre. O timeout é o que transforma o silêncio em erro, e só então as
três tentativas do ADR-0018 têm o que absorver.

60 s é folgado de propósito: um turn normal leva segundos, e o número existe
para pegar socket morto, não para apertar latência.
"""

RETENTATIVAS = types.HttpRetryOptions(attempts=3, initial_delay=2)
"""ADR-0018 — `modelos/D-02`, opção B.

**Sem isto, UM erro transitório derruba o turno inteiro.** Medido no spike 2.4:
com a configuração padrão do ADK, um `429` produz exatamente **uma** requisição
e levanta exceção. A causa está no SDK, não no ADK — quando `retry_options` é
`None`, a política de tentativas é literalmente
`{'stop': stop_after_attempt(1), 'reraise': True}`
(`google/genai/_api_client.py:677-678`).

O risco que isto endereça é o **passo 14 do roteiro**: duas aprovações
simultâneas disparam ~8 chamadas quase ao mesmo tempo, e isso é pico de
requisições **por minuto** — esperar alguns segundos resolve.

E resolve mais do que o ADR previu. Durante a execução do P3, um
`httpx.ReadError` — soluço de rede, não quota — matou um turno inteiro. As
mesmas três tentativas absorvem isso, e é o que mantém os 24 cenários
`@conversa` determinísticos em vez de intermitentes.

⚠️ **`initial_delay=2` é escolha nossa, e precisa ser alto.** O SDK **ignora**
o `retryDelay` que o servidor manda no corpo do erro — medido: três tentativas
em 0,17 s com `initial_delay` baixo. Com espera curta, "tentar de novo" vira
três recusas em sequência: mitigação de aparência.
"""


class ModeloDesconhecido(ValueError):
    """O nome do modelo não está na lista do projeto.

    Tipo próprio porque a falha que ele previne é específica: o `LLMRegistry`
    do ADK **aceita** qualquer `gemini-*` na construção e só quebra na primeira
    chamada, com `404` — ou seja, no meio da conversa do avaliador. Restrição
    `M-7`, medida no spike 2.4.
    """


def criar_modelo(*, nome: str = MODELO, chave: str | None = None) -> Gemini:
    """Monta o modelo dos agentes, validando o nome e injetando a chave.

    ⚠️ **A validação do nome é o que torna a `M-7` imposta por CÓDIGO.** Antes
    dela, a restrição vivia só num cenário; agora um nome errado não sobe. O
    cenário `O modelo de cada agente é um nome de modelo conhecido` continua
    valendo como rede sobre a árvore montada.

    A lista também exclui modelos **sem plano gratuito** (`M-3`), porque a
    chave é do avaliador: um modelo pago não falharia por digitação — falharia
    na correção de quem não paga.
    """
    if nome not in MODELOS_CONHECIDOS:
        raise ModeloDesconhecido(
            f"O modelo {nome!r} não está na lista do projeto "
            f"({sorted(MODELOS_CONHECIDOS)}).\n"
            "O ADK aceitaria esse nome na construção e só falharia na primeira "
            "chamada, com 404, no meio da conversa. Ver M-7 e M-3, no spike 2.4."
        )

    if chave is None:
        import os

        chave = obter_configuracao().google_api_key or os.getenv("GOOGLE_API_KEY", "")
    if not chave:
        raise ChaveDeApiAusente(MENSAGEM_SEM_CHAVE)

    # ⚠️ `client_kwargs` e NÃO o `os.environ`. Verificado: a chave atravessa
    # daqui até uma chamada real ao Gemini. Trocar por `Gemini(model=...)` sem
    # chave faz o ADK voltar a procurar no ambiente e falhar com a chave no
    # `.env` — o bug que este módulo existe para fechar.
    return Gemini(
        model=nome,
        client_kwargs={
            "api_key": chave,
            # ⚠️ O timeout vem JUNTO com o retry, e não em vez dele. Um
            # protege do erro, o outro do silêncio — ver `TEMPO_LIMITE_MS`.
            "http_options": {"timeout": TEMPO_LIMITE_MS},
        },
        retry_options=RETENTATIVAS,
    )
