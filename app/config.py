"""Configuração da aplicação, lida do ambiente / `.env`."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# .../app/config.py -> .../app -> raiz do repositório
RAIZ_DO_PROJETO = Path(__file__).resolve().parent.parent

# ─────────────────────────────────────────────────────────── modelo (ADR-0017)

MODELO = "gemini-3.5-flash-lite"
"""O modelo dos **quatro** agentes. ADR-0017.

**Um lugar só, e isso é parte da decisão.** Com os quatro agentes no mesmo
modelo, o nome repetido em quatro arquivos é a forma mais barata de a
uniformidade se perder sem ninguém notar.

A escolha é de **aritmética**, não de qualidade: o plano gratuito dá **20
requisições por dia** nos modelos da família Flash, e o roteiro do avaliador
custa 70 a 85 chamadas — com qualquer Flash, a correção morre por volta do
passo 5. Os Flash-Lite dão 500/dia.
"""

MODELOS_CONHECIDOS = frozenset({
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
})
"""Os únicos nomes de modelo que este projeto aceita.

⚠️ **Esta lista protege duas restrições, e nenhuma delas é óbvia.**

**`M-7` — erro de digitação não falha ao subir.** Medido no spike 2.4: o
`LLMRegistry` do ADK só recusa nomes que **não** começam com `gemini-`.
`'gemini-9.9-inexistente'` e até `'gemini-'` são aceitos na construção do
agente e resolvem para a classe `Gemini`. O erro aparece na **primeira
chamada**, com `404` — ou seja, no meio da conversa do avaliador, com a
correção em andamento.

**`M-3` — nada pode depender de tier pago.** A chave é do **avaliador**,
preenchida por ele no passo 1. Por isso a lista exclui de propósito os modelos
sem plano gratuito (`gemini-4-argon` é o caso): um modelo desses não falharia
por digitação — falharia na correção de quem não paga, que é pior porque
parece problema do avaliador.

O cenário `O modelo de cada agente é um nome de modelo conhecido` é o que
torna isso verificável, e roda **sem chave de API**.
"""


class Configuracao(BaseSettings):
    """Variáveis de ambiente da aplicação.

    ⚠️ **A versão anterior desta classe afirmava que `GOOGLE_API_KEY` não
    precisava aparecer aqui "porque é lida diretamente pelo `google-genai`".
    Isso era falso, e o erro era silencioso e caro:** o `google-genai` lê
    `os.environ`, e nada neste projeto copiava o `.env` para lá. Com uma chave
    válida no arquivo, `aurora-restaurar` recusava dizendo que não havia
    chave — no passo 1 do roteiro do avaliador, que é exatamente *preencher o
    `.env` e restaurar*. Descoberto ao ligar a geração de embeddings
    (ADR-0020), que foi a primeira coisa do projeto a de fato precisar da
    chave.

    Agora a configuração lê a chave, e quem precisa dela a recebe por
    parâmetro. O cenário `A chave do .env chega a quem gera os embeddings`
    existe para isto não voltar.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    google_api_key: str = ""
    """Chave do Google AI Studio, lida do `.env`.

    Vazia por padrão de propósito: quem precisa dela levanta uma recusa com
    instrução (`ChaveDeApiAusente`), em vez de a aplicação morrer na subida
    por causa de um recurso que talvez não seja usado naquele comando.

    **Nunca versionada.** O `.env` está fora do Git; o `.env.example` traz só
    o nome.
    """

    diretorio_dados: Path = RAIZ_DO_PROJETO / "dados"
    """Onde ficam os JSON do estado inicial do condomínio.

    SOMENTE LEITURA. Nada na aplicação escreve neste diretório: é critério de
    aceite que os arquivos de `dados/` fiquem idênticos aos do repositório base.
    """

    url_banco: str = "postgresql+asyncpg://aurora:aurora@localhost:5433/aurora"
    """URL do Postgres com `pgvector` (ADR-0014). Um banco para tudo.

    **Este é o único lugar que define onde o banco mora.** A aplicação e o
    comando de restauração leem daqui, e isso não é detalhe de organização: se
    cada um tivesse o seu padrão, a restauração limparia um banco e a API
    serviria outro — falha que não aparece em teste, porque cada teste usa um
    schema próprio.

    O driver é **obrigatoriamente assíncrono** (`+asyncpg`): o
    `DatabaseSessionService` do ADK recusa URL de driver síncrono em tempo de
    construção — medido no spike R1 com `sqlite://`, e o mesmo vale aqui.

    A porta é **5433**, não a 5432 padrão, para não colidir com um Postgres já
    instalado na máquina de quem roda o projeto. Bate com o `compose.yaml`.

    Sobrescrevível por variável de ambiente `URL_BANCO`, o que é o caminho para
    apontar a suíte ou a aplicação para outro banco sem editar código.
    """


@lru_cache(maxsize=1)
def obter_configuracao() -> Configuracao:
    return Configuracao()
