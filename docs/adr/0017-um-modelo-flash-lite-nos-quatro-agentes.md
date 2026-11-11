# ADR-0017 — Os quatro agentes usam o mesmo modelo: `gemini-3.5-flash-lite`

**Status:** aceito
**Data:** 2026-11-08
**Origem:** [`docs/spike-2.4-modelos-gemini.md`](../spike-2.4-modelos-gemini.md) → `modelos/D-01`
**Invariantes e garantias afetados:** nenhum invariante do domínio. Afeta a **viabilidade da correção inteira**: sem quota, nenhum passo do roteiro do avaliador responde.
**Relacionado:** ADR-0007 e ADR-0008 (definem quais agentes existem e como são acionados — é essa topologia que multiplica o custo em chamadas) · ADR-0018 (o que fazer quando o `429` acontece de todo jeito)

## Contexto

O assistente tem quatro agentes: um **principal**, que só roteia, e três especialistas — **Reservas**, **Visitantes** e **Regulamento**. Cada um recebe um modelo Gemini por string (`model="..."`). O enunciado deixa a escolha livre, e ela parecia administrativa.

Não é. A investigação da 2.4 mediu duas coisas que, juntas, transformam a escolha num cálculo:

**Um turno de conversa custa 4 chamadas ao modelo, não 1.** Medido com um LLM roteirizado: numa pergunta que o principal encaminha a um especialista que usa uma ferramenta, o principal é chamado 2 vezes e o especialista 2 vezes; cada ferramenta a mais no mesmo turno soma 1. O roteiro do avaliador tem ~18 requisições que invocam o modelo, o que dá **70 a 85 chamadas** numa correção. Esse fator é consequência da topologia já decidida (ADR-0008), não da escolha de modelo.

**O plano gratuito dá 20 requisições por dia na família Flash, e 500 nos Flash-Lite** — por **dia**, contadas por projeto **e por modelo**, com reset à meia-noite do Pacífico. Com qualquer Flash, a correção morre por volta do passo 5, antes da primeira confirmação. O modelo "melhor" é o que reprova.

**Duas restrições fecham metade do espaço de design antes de a decisão ser lida.** A `M-1` proíbe a família Flash — 20 requisições por dia contra 70–85 de uma correção. A `M-3` diz que não se pode contar com tier pago, porque **a chave é do avaliador**, preenchida por ele no passo 1 do roteiro: não há como habilitar faturamento, subir de tier ou aumentar quota. Juntas, elas eliminam o desenho mais intuitivo — "Flash no principal, que decide o caminho; Flash-Lite nos especialistas" —, porque os dois primeiros turnos do avaliador já consumiriam um terço do balde diário do principal. O que sobra são os **Flash-Lite**, e a pergunta real passa a ser **quantos** deles, já que o balde é por modelo e dois modelos são dois baldes.

## Decisão

**Os quatro agentes — principal, Reservas, Visitantes e Regulamento — declaram o mesmo modelo: `gemini-3.5-flash-lite`.** Um nome de modelo no projeto inteiro, num só lugar de configuração.

Nenhum agente é construído sem `model=` (`M-2`): o padrão do ADK é `gemini-3.5-flash`, que roteia para `gemini-3.8-flash` — o balde de 20/dia — e cair nele não emite aviso nenhum.

## Alternativas consideradas

- **Dois Flash-Lite divididos por volume de chamadas** (principal em `gemini-3.5-flash-lite`, os três especialistas em `gemini-3.1-flash-lite`). Era a **recomendação do spike**: o principal responde por metade das chamadas (2 de 4 por turno, medido), então a divisão fica perto de 50/50 e dá ~1.000 requisições por dia mais o dobro de folga de RPM — de graça, só mudando a string. Rejeitada em favor da uniformidade: custa dois nomes de modelo para explicar e justificar no README, e `gemini-3.1-flash-lite` é a geração anterior, de forma que um especialista respondendo pior passa a ter uma variável a mais entre causa e sintoma.
- **Dois Flash-Lite divididos por domínio** (Regulamento no modelo mais antigo, o resto no mais novo). O Regulamento tem a tarefa mais fácil — redigir uma frase curta a partir de um artigo já recuperado. Rejeitada por ganhar pouco: os turnos de regulamento são minoria no roteiro (o passo 12 é um), então o alívio de quota é pequeno e paga-se o mesmo preço de ter dois modelos.
- **Família Flash em qualquer agente.** Eliminada pela restrição `M-1`, por aritmética e não por qualidade: 20 requisições por dia contra 70–85 de uma correção.
- **Qualquer desenho que dependa de tier pago** (`gemini-4-argon`, que não tem plano gratuito, ou Flash com faturamento ligado). Eliminado pela restrição `M-3`: a chave é do avaliador.

## Consequências

**O que fica mais fácil:** um nome de modelo para explicar no README, que é item avaliado. Comportamento **uniforme** entre os agentes: um problema de roteamento não se confunde com diferença de modelo, e é o Flash-Lite mais recente — o de melhor qualidade entre os viáveis. A configuração fica num lugar só, o que torna trocar de modelo uma edição de uma linha.

**O que fica mais difícil, ou passa a custar atenção:** os quatro agentes dividem **um** balde. O limite de RPM (10–15, segundo as fontes) é compartilhado, então o pico do passo 14 — duas aprovações simultâneas, ~8 chamadas quase juntas — cabe, mas sem a folga que dois modelos dariam. É esse estreitamento que o ADR-0018 endereça.

**Risco aceito, e é explícito:** **um só balde de 500 requisições por dia para tudo.** Uma correção gasta ~15% dele; depurar o roteiro várias vezes no mesmo dia encosta no limite, e o reset é à meia-noite do Pacífico. A alternativa rejeitada dobraria essa margem **de graça** — era literalmente uma string diferente — e foi recusada em favor da uniformidade de comportamento e de um README mais simples. Aceita-se porque o único cenário que reprova é "o avaliador roda o roteiro mais de seis vezes no mesmo dia", e porque a válvula é conhecida: dividir os agentes em dois modelos continua sendo uma edição de uma linha por agente.

**Dependência não verificada, e ela sustenta a conta inteira:** os números **20/dia** e **500/dia** vêm de **duas medições independentes de terceiros, que concordam — não do Google**, que parou de publicar os limites do plano gratuito (a página oficial manda olhar *"View your active rate limits in AI Studio"*, que é autenticado e, pior, é do projeto do avaliador). Uma das fontes descreve o método — ler `quotaId` e `quotaValue` do corpo do próprio `429` —, o que dá o limite real e não um piso observado; as duas divergem só no RPM dos Flash-Lite (10 contra 15), e os dois valores comportam o pico do passo 14. Confirmar exige uma chave no `.env`, que não existe neste ambiente. **Se os números estiverem errados, esta decisão muda.**

## Verificação

| Cenário | Protege | Tipo |
|---|---|---|
| Os quatro agentes declaram o mesmo modelo | a decisão deste ADR | **regressão** — falha se alguém dividir os agentes em dois modelos sem registrar |
| Nenhum agente usa um modelo da família Flash | `M-1` | **regressão** — falha se alguém "melhorar" o modelo do principal |
| Nenhum agente herda o modelo padrão do ADK | `M-2` | **regressão** — falha se um agente for construído sem `model=` |
| O modelo de cada agente é um nome de modelo conhecido | `M-7` | **regressão** — falha no erro de digitação, que de outra forma só apareceria como `404` no meio da conversa do avaliador |

Arquivo: `tests/features/modelos.feature`

Os quatro rodam **sem chave de API**: inspecionam a árvore de agentes montada, no marcador `@estrutura`.

## Onde isso vive no código

| O quê | Onde |
|---|---|
| O nome do modelo, num lugar só | `app/config.py` → `MODELO` |
| A fábrica que constrói e valida | `app/agentes/modelo.py` → `criar_modelo` |
| `model=` explícito nos quatro | `app/agentes/principal.py` e `especialistas.py` |
| A lista de nomes de modelo aceitos | ao lado da constante acima, em `app/config.py` |

**O conteúdo da lista de nomes aceitos foi decidido em 2026-11-08**, e ele não
é só o modelo em uso: a lista contém **`gemini-3.5-flash-lite` e
`gemini-3.1-flash-lite`, e nada mais**. Ela recusa de propósito os modelos
**sem plano gratuito** — `gemini-4-argon` é o caso.

Isso faz o cenário `O modelo de cada agente é um nome de modelo conhecido`
proteger **duas** restrições em vez de uma:

- **`M-7`** — qualquer `gemini-*` inventado é aceito na construção do agente e
  só quebra na **primeira chamada**, com `404`, no meio da conversa do
  avaliador. A lista move essa falha para a suíte.
- **`M-3`** — a chave é do avaliador, e nada pode depender de tier pago. Um
  modelo fora do plano gratuito **não** falharia por digitação: falharia na
  correção de quem não paga, que é pior porque parece problema do avaliador.

A `M-3` era, até esta decisão, a restrição **menos protegida** do spike 2.4 —
nada em código pode inspecionar o tier da conta de outra pessoa. A lista não
resolve isso (continua impossível), mas remove a única forma de violá-la por
dentro: escolher um modelo que o plano gratuito não atende.

⚠️ **O modelo é um OBJETO construído por nós, não a string.** Passar
`model="gemini-3.5-flash-lite"` ao `LlmAgent` **não funciona neste projeto**:
o ADK monta o cliente internamente e lê `GOOGLE_API_KEY` do `os.environ` — e o
`.env` não chega lá. O resultado é `ValueError: No API key was provided`, com a
chave sentada no arquivo. É o **mesmo bug** que o ADR-0020 registrou para os
embeddings, aparecendo pela segunda vez em outro lugar.

⚠️ **A validação do nome tornou a `M-7` imposta por CÓDIGO.** `criar_modelo`
recusa nome fora de `MODELOS_CONHECIDOS`, então um erro de digitação **não
sobe** — antes ele era aceito na construção e só quebrava na primeira chamada,
com `404`, no meio da conversa do avaliador. O cenário continua existindo como
rede sobre a árvore montada.

Um objeto só, compartilhado pelos quatro agentes: não há como dois divergirem
de modelo, porque não há dois modelos.

Verificado por 4 cenários `@estrutura` em `tests/features/modelos.feature`,
todos rodando **sem chave de API**.

O ponteiro único em `app/config.py` é parte da decisão, não detalhe: com os
quatro agentes no mesmo modelo, o nome repetido em quatro arquivos é a forma
mais barata de a uniformidade se perder sem ninguém notar.
