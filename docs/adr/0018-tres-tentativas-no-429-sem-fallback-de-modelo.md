# ADR-0018 — Cada modelo tenta três vezes no `429`, com 2 s de espera inicial; `FallbackModel` fica de fora

**Status:** aceito
**Data:** 2026-11-08
**Origem:** [`docs/spike-2.4-modelos-gemini.md`](../spike-2.4-modelos-gemini.md) → `modelos/D-02`
**Invariantes e garantias afetados:** nenhum invariante do domínio. Protege a **Garantia 5** por um caminho oblíquo: o passo 14 do roteiro exige que duas aprovações simultâneas respondam `200`, e um `429` por pico de requisições por minuto reprovaria o passo sem nenhuma recusa de negócio acontecer.
**Relacionado:** ADR-0017 (define o modelo em que o retry é configurado) · ADR-0019 (o que a API faz quando o retry não basta) · ADR-0011 (recusa de negócio nunca vira erro de servidor — aqui o erro **não** é de negócio)

## Contexto

Mesmo com o modelo certo (ADR-0017), um `429 RESOURCE_EXHAUSTED` pode acontecer por **pico de requisições por minuto**. O roteiro do avaliador produz exatamente isso: o **passo 14** dispara duas sessões aprovando uma reserva ao mesmo tempo, o que, a 4 chamadas por turno, é um pico de cerca de **8 chamadas ao modelo quase simultâneas** contra um limite de 10–15 por minuto. O pico em si cabe; o que não cabe é o pico **somado** ao que foi gasto nos segundos anteriores, se o avaliador percorrer os passos depressa. Isso é **RPM**, não quota diária — e esperar alguns segundos resolve.

A medição mostrou que, com a configuração padrão do ADK, **esperar não acontece**: um único `429` isolado derruba o turno inteiro. São **1 requisição** HTTP e uma `_ResourceExhaustedError`, sem nenhuma nova tentativa. A causa está no SDK, não no ADK: em `google/genai/_api_client.py:677-678`, a função que monta a política de tentativas devolve `{'stop': stop_after_attempt(1), 'reraise': True}` quando `retry_options` é `None` — literalmente "nunca tente de novo". E `None` é o padrão de `Gemini.retry_options` (`google/adk/models/google_llm.py:188`).

Com `retry_options=HttpRetryOptions(attempts=3)`, o mesmo harness mediu: um `429` seguido de `200` termina em **resposta normal**, com 2 requisições. É uma linha de configuração que converte uma reprovação evitável em nada.

Existe uma segunda mitigação, medida e funcional, que resolve um problema **diferente**: `FallbackModel(models=[...])` tenta os modelos em ordem e passa ao seguinte quando o primeiro falha com um código da sua lista — `429` está nela por padrão (verificado com controle: tirando o `429` da lista, o fallback não acontece). Como a quota diária é contada por projeto **e por modelo**, uma cadeia de dois modelos é uma cadeia de dois baldes. Ou seja: `retry_options` resolve pico de RPM; `FallbackModel` resolve **quota diária esgotada**, que a espera não resolve.

## Decisão

**Cada modelo é construído com `retry_options=types.HttpRetryOptions(attempts=3, initial_delay=2)`.** Vale para os quatro agentes, que usam o mesmo modelo (ADR-0017).

**`FallbackModel` fica de fora.**

A espera inicial de **2 s** é escolha deliberada, e o motivo está na armadilha abaixo: não é um valor "padrão razoável", é o mínimo para a nova tentativa ter chance de encontrar a janela de RPM aberta.

## Alternativas consideradas

- **Não fazer nada; deixar o padrão do ADK.** Zero código, e a falha é alta e visível em vez de silenciosa. Rejeitada porque o modo de falha medido — caso **D** do harness: um `429` isolado, com `200` disponível na tentativa seguinte, derrubando o turno — é o único cenário de reprovação deste spike que uma linha de configuração elimina por completo.
- **`FallbackModel` em todos os agentes**, numa cadeia de dois Flash-Lite. Medido e funcional, e cobre o caso que o retry **não** cobre: balde diário esgotado. Rejeitada por três motivos, e o terceiro é decisivo: (1) o recurso é **experimental** no ADK 2.14 e emite `UserWarning: [EXPERIMENTAL] feature FALLBACK_MODEL is enabled` — funciona sem habilitação, mas o contrato pode mudar; (2) `FallbackModel.model` reporta o nome do **primário**, então qualquer log ou evento que use esse campo **mente sobre quem respondeu**; (3) **não está medido o que ele faz com ferramenta que exige confirmação** — e é exatamente aí que este projeto já se queimou. A armadilha do `AgentTool` (restrição `R1`) foi precisamente um embrulho que parecia neutro, descartava a sessão aninhada e fazia a pendência nunca chegar à API, **sem erro nenhum**. "Em princípio `FallbackModel` embrulha o modelo, não o agente" é o mesmo tipo de frase que o `AgentTool` já desmentiu aqui.
- **`retry_options` mais `FallbackModel`** (o próprio ADK documenta a composição em `_fallback_model.py:210-212`). Cobriria os dois modos de falha. Rejeitada porque herda o risco não medido acima e porque o pior caso de latência soma: 3 tentativas no primário, depois 3 na reserva, o que no pico dá cerca de 12 s antes de responder.

> **`FallbackModel` segue disponível como válvula**, não descartado. A condição para adotá-lo é **medir antes de confiar**: um turno de reserva com `require_confirmation`, aprovado após reinício do processo, com `FallbackModel` no lugar — o mesmo teste que o spike R1 fez e que o ADR-0014 repetiu como primeiro passo, pela mesma razão: a falha é silenciosa.

## Consequências

**O que fica mais fácil:** o pico de RPM do passo 14 deixa de ser fatal. O risco que o enunciado nomeia — *"estourar quota vira 500 e reprova"* — fica coberto na sua forma transitória, que é a provável, por uma linha por modelo.

**O que fica mais difícil, ou passa a custar atenção:** o turno pode levar ~6 s a mais no pior caso, e o `curl` do avaliador espera calado. E quando a quota **diária** acabar, o retry não ajuda: ele gasta **três** requisições onde antes gastava uma, o que torna o fim do balde um pouco mais rápido. É o custo de cobrir o caso transitório.

**Armadilha a registrar, porque ela transforma a mitigação em teatro se for ignorada:** o SDK **ignora o `retryDelay` que o servidor manda** no corpo do erro. O `429` do Gemini traz um `google.rpc.RetryInfo` com, por exemplo, `retryDelay: "25s"`; o harness mediu **3 tentativas em 0,17 s** com `initial_delay` baixo. A espera é inteiramente escolha nossa, e um `initial_delay` curto transforma "tentar de novo" em **três recusas em sequência** — mitigação de aparência, que passa em revisão de código e não protege nada. Daí o `initial_delay=2`.

**Risco aceito:** **quota diária esgotada continua derrubando o turno.** A mitigação que resolveria esse caso é justamente a que foi recusada, e a recusa é por falta de medição, não por o problema não existir. Se o avaliador chegar com o balde do dia gasto, nenhuma configuração deste ADR salva a correção — o que sobra é o ADR-0019, que faz a falha ter uma assinatura honesta em vez de se disfarçar.

## Verificação

| Cenário | Protege | Tipo |
|---|---|---|
| Um `429` transitório não derruba o turno | a decisão deste ADR, e o passo 14 | **regressão** — falha se `retry_options` sair da construção do modelo |
| Um `429` persistente produz três tentativas ao modelo, não uma | `attempts=3`, contra o `stop_after_attempt(1)` que o SDK usa quando `retry_options` é `None` | **regressão** — é a observação que distingue esta decisão da alternativa "não fazer nada" |

Arquivo: `tests/features/modelos.feature`

Os dois rodam **sem chave de API**: o que eles precisam é de um endpoint que responda `429`, que o harness do spike já tem (`scratchpad/spike24/h1_quota.py`).

> Não há cenário para a rejeição do `FallbackModel`. A diferença entre adotá-lo e
> não adotá-lo só aparece quando um balde de quota real se esgota, que é
> observação que nenhum teste deste repositório alcança — e o risco que motivou
> a recusa é precisamente o que **não está medido**. Registrar isso é mais
> honesto que escrever um cenário decorativo.

## Onde isso vive no código

| O quê | Onde |
|---|---|
| Construção do modelo com `retry_options` | `app/config.py` ou `app/agentes/modelo.py` → a fábrica que os quatro agentes chamam |
| `attempts=3, initial_delay=2` | o mesmo lugar, com comentário citando este ADR e o `retryDelay` ignorado |

⚠️ **O `retry_options` sozinho NÃO basta, e isso foi medido nesta
implementação.** Ele reage a **erro** — e o modo de falha mais comum não é
erro, é **silêncio**: um socket pendurado espera para sempre e a retentativa
nunca dispara.

Aconteceu de verdade: a suíte ficou **4min26 com 13 segundos de CPU** — 97%
parada — e **12 conexões ao Google abertas e penduradas**, nenhuma delas com
erro. O que faltava era `timeout`, em `app/agentes/modelo.py` →
`TEMPO_LIMITE_MS` (60 s). **O timeout é o que transforma silêncio em erro**, e
só então as três tentativas têm o que absorver. Os dois andam juntos; separar
um do outro deixa o buraco aberto.

O `initial_delay=2` precisa de comentário no código apontando para este ADR. Sem
ele, o número parece arbitrário e a primeira pessoa que quiser "deixar o teste
mais rápido" o baixa para `0.1` — o que mantém a configuração e destrói a
mitigação, sem nenhum teste ficando vermelho.
