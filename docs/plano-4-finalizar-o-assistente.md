# Plano: ligar os agentes, abrir as rotas de conversa e fechar os 51 cenários pendentes

**Status:** executado em 2026-11-09
**Origem:** o que resta do [`TODO.md`](../TODO.md) — Fases 3.2, 4 e 5 — mais as decisões já registradas dos spikes [1.2](spike-1.2-fronteiras-agentes.md), [1.3](spike-1.3-superficie-de-tools.md), [1.4](spike-1.4-estrategia-regulamento.md), [1.6](spike-1.6-guardrails.md), [2.4](spike-2.4-modelos-gemini.md), [3.2](spike-3.2-rotas-de-conversa.md) e [R1](spike-R1-confirmacao-de-tools.md)
**Implementa:** ADR-0007, 0008, 0009, 0011 (a metade que falta), 0013 (a metade que falta), 0015, 0016, 0017, 0018, 0019, 0021

---

## O que este plano constrói

O **Residencial Aurora** é um assistente de condomínio: pelo chat, o morador
reserva áreas comuns, cancela as próprias reservas, autoriza visitantes e tira
dúvidas sobre o regulamento. Um avaliador corrige rodando 15 passos contra a
API.

Hoje o projeto tem **tudo decidido e metade construído**. O que já funciona, e
funciona de verdade — rodando fora de teste:

| Em uso hoje | Prova |
|---|---|
| Postgres com `pgvector`, schema, os dois índices de invariante | `docker compose up` + `uv run aurora-restaurar` |
| As 7 ferramentas de domínio e o portão de confirmação | 17 cenários `@ferramenta` verdes |
| Os 96 artigos do regulamento vetorizados | `aurora-restaurar` imprime "96 artigos vetorizados" |
| A API com as 4 rotas de verificação | `curl localhost:8000/apartamentos/101/reservas` |

E o que **não existe**, sem rodeio:

- **nenhum `LlmAgent` foi construído neste repositório.** `app/agentes/` tem as
  ferramentas e o portão, nada mais;
- **nenhuma rota de conversa.** `POST /sessoes/{id}/mensagens` e
  `/confirmacoes` não existem;
- **a sessão da aplicação é em memória.** `criar_app` monta
  `ServicoSessaoEmMemoria`, implementação temporária — os eventos de uma
  conversa morrem com o processo. O `DatabaseSessionService` está **provado**
  que funciona contra este Postgres (`tests/processo_retomada.py`), mas nunca
  foi ligado na aplicação;
- **nenhuma ferramenta consulta os vetores.** Eles existem e ninguém os lê.

Quando este plano terminar, o morador conversa com o assistente pela API, as
confirmações passam pela rota de confirmações, e os **51 cenários `@pendente`
ficam verdes** — a suíte inteira passa a cobrar comportamento em vez de
ausência.

## O que fica de fora

| Não entra | Por quê |
|---|---|
| **Qualquer decisão nova** | Todas as 32 decisões dos spikes estão preenchidas. Se um passo exigir escolher algo, ele para e volta como pendência — ver *Riscos*. |
| **`ResumabilityConfig(is_resumable=True)`** | Decidido **desligado** (`R1/D-04`, 2026-11-08): nada no roteiro exige, é *best-effort* por documentação do ADK, e exigiria tools idempotentes que ninguém escreveu pensando nisso. |
| **Recusar mensagem nova com pendência aberta** | `rotas/D-04` decidiu **processar normalmente**. Zero linhas. A pendência duplica e nada executa, que é o que o enunciado permite. |
| **Índice vetorial (`hnsw`/`ivfflat`)** | Para 96 artigos a varredura exata é instantânea. `vector(768)` preserva a opção; usá-la não se justifica. |
| **Limpar pendências equivalentes** | Consequência aceita de `rotas/D-04`. Se incomodar depois da Fase 5, é um `if` na rota. |

## O estado final, em uma frase

> O avaliador percorre os 15 passos contra a API, e a suíte fecha com **95
> cenários verdes e zero `@pendente`**.

Para isso ser verdade, precisa passar a existir: os quatro agentes; a
ferramenta de busca no regulamento; a sessão do ADK em Postgres ligada na
aplicação; uma tabela que diga de que apartamento é cada conversa; as duas
rotas de conversa; o tratamento de quota; e a implementação dos passos de
teste, que hoje não existe para nenhum cenário `@conversa`, `@estrutura`,
`@api` novo ou `@recuperacao`.

---

## Passos

### P1 — A busca no regulamento devolve artigos

**Implementa:** ADR-0021, e completa ADR-0015 e o ADR-0016
**Depende de:** —

**Entrega:**
- `app/infra/recuperacao.py` — a consulta por proximidade:
  `ORDER BY embedding <=> :vetor LIMIT 3`, descartando os abaixo de **0,65**
- `app/agentes/ferramentas/regulamento.py` → `buscar_no_regulamento(assunto)`,
  devolvendo dicionário nomeado com a lista de artigos e o capítulo de cada um
- os passos de teste dos 7 cenários `@recuperacao`

**Pronto quando:** ficam verdes os 7 `@recuperacao` de `regulamento.feature`.

**Risco:** o corte de 0,65 foi medido em **nove** perguntas. Se um dos 7
cenários cair do lado errado do corte, o número volta à mesa — e isso é
decisão, não ajuste: mexer no corte sem registrar é exatamente o que o
ADR-0021 existe para impedir.

> **Por que é o primeiro passo.** Ele não depende de agente nenhum: os
> cenários `@recuperacao` chamam a ferramenta direto. É a única frente deste
> plano que fica verde sem chave de API e sem runner, então falha barato.

---

### P2 — Os quatro agentes existem, com o modelo certo

**Implementa:** ADR-0007, ADR-0008, ADR-0009, ADR-0017, e completa o ADR-0011
**Depende de:** P1 — o especialista de Regulamento precisa da ferramenta

**Entrega:**
- `app/agentes/principal.py` — o roteador, **sem** ferramenta de domínio e
  **sem** o regulamento nas instruções (ADR-0009)
- `app/agentes/reservas.py` e `visitantes.py` — `sub_agents`,
  `mode="single_turn"` (⚠️ `AgentTool` aqui mata a confirmação, restrição `R1`)
- `app/agentes/regulamento.py` — embrulhado em `AgentTool`, que é o que isola
  o trecho do histórico (Garantia 4)
- `app/config.py` — o nome do modelo num lugar só, e a **lista de nomes
  aceitos**: apenas `gemini-3.5-flash-lite` e `gemini-3.1-flash-lite`
- `on_tool_error_callback` registrado **em cada agente** — é a metade do
  ADR-0011 que faltava, e a rede que impede qualquer exceção de virar `500`
- os passos de teste dos 8 cenários `@estrutura`

**Pronto quando:** ficam verdes os 8 `@estrutura` — 4 de `agentes.feature` e 4
de `modelos.feature`.

**Risco:** `AgentTool` em Reservas ou Visitantes quebra a Garantia 1 **sem
erro nenhum** — a pendência não aparece e a ação não executa. É a armadilha
mais caro-de-errar do projeto. Os cenários `@estrutura` **não pegam isso**:
eles inspecionam a árvore, e uma árvore errada ainda é uma árvore. Quem pega é
o P4.

---

### P3 — A API conversa, e a conversa sobrevive ao reinício

**Implementa:** `rotas/D-01`, `D-02`, `D-04`, as regras `A-3`, `A-5`, `A-7`,
`A-9`, e completa o ADR-0014 na parte da **sessão**
**Depende de:** P2

**Entrega:**
- `app/infra/banco.py` — tabela `conversa` com `session_id` e `apartamento`
  (`rotas/D-02`, opção A)
- `app/api/aplicacao.py` — `DatabaseSessionService` no lugar de
  `ServicoSessaoEmMemoria`, e `App` + `Runner` com resumability **desligado**
- `POST /sessoes` — grava a ligação **depois** de o ADK confirmar a criação.
  A ordem é a mitigação de `rotas/D-02`: o pior caso passa a ser uma conversa
  órfã do ADK, não um `session_id` que a API aceita e o ADK não acha
- `app/api/dependencias.py` → `obter_sessao_existente` lendo a nossa tabela
- `POST /sessoes/{id}/mensagens` — e quatro regras que não são detalhe:
  - **`A-7`** os events são lidos **até o fim**, de propósito, para o erro de
    quota virar exceção em vez de `200` com resposta vazia
  - **`A-9`** `resposta` recebe **só** o texto do agente principal; o texto
    dos especialistas é descartado pela rota
  - **`A-5`** o campo `resposta` **nunca** recebe frase escrita pelo nosso
    código. Vazio é informação: significa "parei esperando confirmação"
  - **`A-3`** a lista de pendências é montada **depois** do turn, varrendo a
    conversa inteira
- `app/api/pendencias.py` — a varredura que calcula as confirmações abertas de
  uma conversa: percorre os events, acha os pedidos de aprovação e descarta os
  já respondidos (`rotas/D-03`, opção A; é o que a regra `R6` descreve)
- um cenário que compara a nossa varredura com a função interna do ADK
  (`index_open_interrupts`), que é a opção B usada como **juiz**: ele pega de
  graça uma mudança de formato dos events no dia em que alguém atualizar a
  versão fixada
- os passos de teste dos 24 cenários `@conversa` desta fatia

**Pronto quando:** ficam verdes os 24 `@conversa` listados na tabela do fim —
8 de `agentes.feature`, 7 de `guardrails.feature`, 3 de `regulamento.feature`,
5 de `reservas.feature` e 1 de `sessao.feature`.

**Risco:** é o passo mais gordo do plano, e isso é deliberado — a rota não
funciona sem a sessão persistida, e a sessão persistida não é observável sem a
rota. Separá-los daria um passo sem critério de pronto verificável. **Se ele
ficar vermelho, a causa pode estar em três lugares** (tabela, serviço de
sessão, rota), e é por isso que o `A-7` e o `A-9` estão escritos como regras
nomeadas: para o diagnóstico ter onde se apoiar.

**Segundo risco, e ele é de quota:** 24 cenários `@conversa` a ~4 chamadas ao
modelo cada dão da ordem de **100 chamadas por rodada da suíte**, contra 500
por dia do plano gratuito. Rodar a frente inteira três vezes num dia encosta
no limite. Durante o desenvolvimento, rodar por arquivo.

---

### P4 — A rota de confirmações aprova, nega e recusa o que não é dela

**Implementa:** Garantia 1, as regras `A-1`, `A-2`, `A-4`, `A-8`, a restrição
`R5`, e completa o ADR-0013
**Depende de:** P3

**Entrega:**
- `POST /sessoes/{id}/confirmacoes`, injetando um `FunctionResponse` autorado
  por `"user"` com o `id` da pendência (`R5`) — **nunca** reusando o caminho
  de texto da rota de mensagens, que não retoma nada (`A-4`)
- **`A-1`** o `409` é decidido **antes** de acionar o ADK. Depois é tarde: dá
  `500`
- **`A-2`** a pergunta que decide o `409` é uma só: esse `id` está pendente
  **nesta** conversa?
- **`A-8`** `detalhes` montado **campo por campo** — `area` e `data` para
  reserva, `nome` e `data` para visitante. Nunca `originalFunctionCall.args`
  cru: é a metade do ADR-0013 que faltava, e é o que impede um `apartamento`
  inventado pelo modelo de chegar à resposta
- os passos de teste dos 7 cenários desta fatia

**Pronto quando:** ficam verdes:
- `A confirmação de reserva retoma no especialista de Reservas`
- `A confirmação de visitante retoma no especialista de Visitantes`
- `Confirmar pela conversa não executa a ação`
- `Argumento inventado pelo modelo não aparece nos detalhes da pendência`
- `Argumento inventado não vaza pela confirmação pendente`
- `Reenviar uma confirmação já respondida não executa de novo`
- `Responder um id de confirmação que não é desta sessão`

**Risco:** **é aqui que a armadilha do `R1` aparece, e só aqui.** Se Reservas
ou Visitantes tiver ficado como `AgentTool` no P2, estes cenários falham e
nenhum dos anteriores falhou. Os dois cenários de retomada por especialista
existem porque o spike R1 mediu com **um** agente de confirmação, e agora são
**dois** — o roteador precisa acertar entre eles, e isso nunca foi medido.

---

### P5 — Quota esgotada falha alto, e um pico não derruba o turno

**Implementa:** ADR-0018, ADR-0019
**Depende de:** P3 (a rota precisa existir para devolver `503`)

**Entrega:**
- `retry_options=types.HttpRetryOptions(attempts=3, initial_delay=2)` em cada
  modelo (ADR-0018). ⚠️ O SDK **ignora** o `retryDelay` que o servidor manda —
  medido: 3 tentativas em 0,17 s com `initial_delay` baixo. O `2` é escolha
  nossa, e `initial_delay` curto viraria três recusas em sequência
- um `exception handler` traduzindo quota esgotada em **`503` com
  `Retry-After`** (ADR-0019)
- o stub HTTP que responde `429`, como fixture da suíte
- os passos de teste dos 5 cenários desta fatia

**Pronto quando:** ficam verdes os 2 `@runner` e os 3 `@api` de
`modelos.feature`.

**Risco:** `Quota esgotada nunca vira resposta vazia` é o cenário mais
importante dos cinco, e o modo de falha que ele evita é silencioso: `200` com
`resposta` vazia é, pelo contrato, o sinal de *"parei esperando confirmação"* —
uma falha de quota se disfarçaria de pendência. Ele depende do `A-7` do P3
estar certo; se o P3 parar de drenar os events, este cenário é o que grita.

---

### P6 — O script de validação percorre os 15 passos

**Implementa:** Fase 5 do `TODO.md`
**Depende de:** P1–P5

**Entrega:** `scripts/validar.py`, executando os passos 1 a 14 em ordem contra
a API no ar e imprimindo pass/fail por asserção. Cobrindo em especial:
- passos 3, 4 e 10 — `RSV-4821`, `Marina Duarte` e `302` isolado ausentes **da
  resposta e dos eventos**
- passo 8 — reenviar o mesmo `id` dá `409` e continua existindo **exatamente
  uma** reserva
- passos 12→13 — contar eventos, reiniciar **sem restaurar**, contar de novo:
  mesmo número, e nova mensagem funciona
- passo 14 — duas aprovações **simultâneas**, ambas `200`, somando **uma**
  reserva

**Pronto quando:** o script roda num clone limpo, do `uv sync` em diante, e
imprime todas as asserções em verde.

⚠️ **O critério deste passo é de outra natureza, e vale dizer em voz alta.**
Os outros cinco têm cenário de suíte; este não. O script **é** o instrumento de
verificação — ele é a régua da nota, não algo que uma régua confere. Escrever um
cenário que verificasse o script seria verificar o verificador, e a Fase 5 do
`TODO.md` o define assim de propósito.

---

### P7 — Fechar o rastro

**Implementa:** —
**Depende de:** P1–P6

**Entrega:**
- *Onde isso vive no código* preenchido em ADR-0007, 0008, 0009, 0017, 0018,
  0019, 0021; e a anotação ⚠️ removida de ADR-0011 e ADR-0013, que passam a
  estar inteiros
- `README.md` — os três marcadores **⬜ não implementado** saem, e a seção
  *Garantias* passa a apontar código que existe. Em especial a Garantia 3, que
  hoje diz em voz alta que está pela metade
- `CLAUDE.md` com qualquer armadilha nova que aparecer no caminho
- `TODO.md` — Fases 3.2, 4 e 5 fechadas

**Pronto quando:** `uv run python scripts/cobertura.py` não acusa ponteiro
quebrado nem ADR sem cenário, e `uv run pytest -q` fecha com **zero
vermelhos**.

**Risco:** —

---

## Ordem e paralelismo

```
P1 (busca) ──► P2 (agentes) ──► P3 (rota de mensagens) ──┬──► P4 (confirmações) ──► P6 ──► P7
                                                          └──► P5 (quota)
```

**P1 primeiro porque é o único que fecha sem chave de API e sem runner.** Se o
corte de 0,65 estiver errado, descobrimos antes de haver agente para culpar.

**P2 depois de P1** porque o especialista de Regulamento precisa da ferramenta
para ser montado.

**P3 depois de P2**, e os dois juntos são o caminho crítico: quase metade dos
cenários pendentes depende dele.

**P4 e P5 podem ir em paralelo**, se houver dois pares de mãos. Os dois só
precisam do P3; não se tocam.

**P6 depois de tudo**, porque ele exercita o sistema inteiro.

## Cenários que este plano faz virar

**Os 51 `@pendente`, e nenhum sobra.**

| Passo | Quantos | Arquivo e camada |
|---|---|---|
| **P1** | 7 | `regulamento.feature` · `@recuperacao` |
| **P2** | 8 | `agentes.feature` (4) e `modelos.feature` (4) · `@estrutura` |
| **P3** | 24 | `agentes.feature` (8), `guardrails.feature` (7), `regulamento.feature` (3), `reservas.feature` (5), `sessao.feature` (1) · `@conversa` |
| **P4** | 7 | `agentes.feature` (2), `guardrails.feature` (4), `ferramentas.feature` (1) · `@conversa` e `@api` |
| **P5** | 5 | `modelos.feature` · `@runner` (2) e `@api` (3) |
| | **51** | |

**Continuam vermelhos:** nenhum. É o ponto deste plano — quando ele terminar,
`uv run pytest -q` fecha com zero vermelhos, e a etiqueta `@pendente` deixa de
existir no projeto.

**O invariante `I-04`** — cobrança ou acesso só após confirmação — hoje é a
única reclamação do `cobertura.py`, por não ter cenário que o cubra. Os
cenários de retomada do P4 passam a cobri-lo; o P7 confere que a reclamação
sumiu.

## Riscos do plano

- **Nenhuma decisão do projeto está em aberto** — conferido spike por spike em
  2026-11-08. A última era a `rotas/D-03`, fechada como **A no código, B num
  teste**: a varredura é nossa, em `app/`, porque a seção *Garantias* do README
  é item avaliado e precisa apontar código nosso; e a função interna do ADK
  entra como juiz num cenário, para avisar se o formato dos events mudar.
  **O risco que sobra dessa escolha** é que a varredura é lógica sobre o
  formato interno dos events do ADK, escrita por nós: se esse formato mudar,
  ela quebra. O cenário comparativo é exatamente a rede contra isso, e é a
  única parte deste plano cujo valor só aparece numa atualização futura de
  versão.

- **A quota diária é o limite mais apertado do projeto.** 500 requisições por
  dia, contra ~100 por rodada da frente `@conversa`. O desenvolvimento do P3 e
  do P4 vai precisar rodar por arquivo, não a suíte inteira. E a chave que o
  avaliador usa é **dele**, não nossa: nada aqui pode depender de tier pago.

- **O roteamento entre dois agentes de confirmação nunca foi medido.** O spike
  R1 mediu a retomada com **um**; o ADR-0007 registra isso como o risco que a
  escolha de três especialistas ampliou. Os dois cenários do P4 são a primeira
  vez que isso é exercido.

- **Nenhum cenário `@conversa` jamais rodou.** Eles são 27, e a implementação
  dos passos deles é trabalho que o plano conta junto com o código de produção.
  A disciplina da `B.5` do `TODO.md` vale aqui: **verificar efeito, não prosa**
  — estado do banco, qual ferramenta foi chamada com quais argumentos, ausência
  de string proibida, presença ou não de pendência. Comparar texto que o modelo
  escreveu dá teste que quebra quando ele reformula, e teste ruidoso acaba
  desligado.

- **O P3 é gordo o suficiente para esconder onde falhou.** Aceito, porque
  cortá-lo produziria um passo sem critério verificável. A mitigação é as
  regras `A-*` nomeadas, para o diagnóstico ter onde se apoiar.

## Execução

| Passo | Estado | Cenários que ficaram verdes |
|---|---|---|
| P1 | ✅ 2026-11-08 | os 7 `@recuperacao` (11 testes, contando os `Esquema do Cenário`) |
| P2 | ✅ 2026-11-08 | os 8 `@estrutura` — 4 de `agentes.feature`, 4 de `modelos.feature` |
| P3 | ✅ 2026-11-09 | os 24 `@conversa` |
| P4 | ✅ 2026-11-09 | os 7 da rota de confirmações |
| P5 | ✅ 2026-11-09 | os 2 `@runner` e 3 `@api` de quota |
| P6 | ✅ 2026-11-09 | `scripts/validar.py` — **59 verificações verdes** |
| P7 | ✅ 2026-11-09 | `cobertura.py` limpo; README sem placeholder |

### P1 — o cenário que virou ADR

**O risco que o plano nomeou aconteceu**, e não foi no corte: foi no
**ranking**. O cenário `Pergunta cuja resposta exige dois artigos` ficou
vermelho. A pergunta *"posso fazer festa com som no salão até 2h"* devolvia
Art. 39, 17 e 37 — e o **Art. 16, que tem o horário, não aparecia nem no top
8**.

A causa é a decisão do ADR-0016: o título do capítulo entra no vetor, então os
8 artigos do *"Capítulo VI: Salão de festas…"* casam com qualquer pergunta que
diga "salão" e enterram o artigo de outro capítulo. **A mesma decisão que faz a
piscina funcionar causava isto.**

Medi quatro formas de corrigir antes de escolher. A vencedora: seguir a
**remissão explícita** — o Art. 39 cita o Capítulo III por escrito, e a frase
da remissão, usada como consulta restrita àquele capítulo, traz o Art. 16 com
**0,8114**. Virou o [ADR-0022](adr/0022-a-busca-segue-remissoes-explicitas-de-capitulo.md),
com as três alternativas rejeitadas e o porquê de cada uma. Alcance pequeno:
**3 dos 96 artigos** citam outro capítulo.

Aumentar o limite de 3 **não** resolveria, e isso foi medido, não suposto: o
Art. 16 não estava no top 8.

**Um bug meu, que vale ficar registrado:** o primeiro passo de teste comparava
capítulo por prefixo de string, e `"Capítulo VIII".startswith("Capítulo VI")` é
`True` — "VIII" começa com "VI". Isso derrubou o cenário do cachorro-na-quadra
**com a recuperação certa**. Numeral romano se compara inteiro, e o mesmo
cuidado está no `LIKE 'Capítulo VI:%'` da consulta, onde o `:` é o que impede a
colisão.

Verificado por duas sabotagens, cada uma derrubando só o que devia: desligar a
remissão derruba 1 cenário; zerar o corte derruba os 3 de pergunta fora de
escopo.

### P2 — os quatro agentes, e uma surpresa boa

Os quatro existem: `app/agentes/principal.py` monta a árvore,
`especialistas.py` tem os três, e `tratador_de_erro.py` fecha a metade que
faltava do ADR-0011.

**O ADK confirmou a medição do spike 2.4 de um jeito que o plano não previu.**
Com `mode="single_turn"`, o ADK **converte os `sub_agents` em ferramentas**:
`principal.tools` traz três itens, não um —
`AgentTool(regulamento)`, `_SingleTurnAgentTool(reservas)` e
`_SingleTurnAgentTool(visitantes)`. É exatamente o que o spike havia medido
("em `single_turn` o especialista é exposto ao principal como FUNÇÃO com o nome
do agente, não como `transfer_to_agent`"), e é o que o cenário chama de "a
transferência". A primeira versão do passo de teste exigia `len(tools) == 1` e
ficou vermelha **com a árvore certa** — bug meu, registrado no código.

**E isso deu um ganho que o plano dizia ser impossível.** O plano afirmava que
os cenários `@estrutura` *"não pegam"* a armadilha do `R1`, porque "uma árvore
errada ainda é uma árvore". Com os sub_agents visíveis em `tools`, dá para
conferir o **tipo** do embrulho — e a asserção que exige
`type(tool) is not AgentTool` para os dois transacionais **pega a armadilha**.
Verificado por sabotagem: trocar Reservas para `AgentTool` derruba o cenário.

O ganho é de velocidade de diagnóstico: a falha mais caro-de-errar do projeto
passou a aparecer em **0,6 segundo, sem chave de API**, em vez de só num
`@conversa`. O cenário de retomada do P4 continua necessário — ele prova que a
confirmação de fato funciona, não só que a árvore está declarada direito.

Verificado por três sabotagens, cada uma derrubando só o que devia: Reservas
como `AgentTool`, modelo trocado por um Flash, e ferramenta de reserva no
agente principal.

### P3 a P7 — o que a execução custou além do previsto

**Quatro bugs reais**, e três deles eram o mesmo problema entrando por portas
diferentes:

1. **A chave não chegava ao ADK.** Com o modelo passado como *string*, ele
   monta o cliente internamente e lê `GOOGLE_API_KEY` do `os.environ` — onde o
   `.env` não chega. É o **mesmo bug** que o ADR-0020 registrou para os
   embeddings, na segunda aparição. Corrigido com um objeto `Gemini` construído
   por nós (`app/agentes/modelo.py`), que de quebra validou o nome do modelo e
   subiu a `M-7` de "teste pega" para "código impede".

2. **Pool de conexão contra event loop, pela terceira vez.** O engine interno
   do `DatabaseSessionService` não é nosso e não usava `NullPool`. Apareceu nos
   passos do `pytest-bdd` (um loop por passo), no `TestClient` (um portal por
   requisição) e no harness de dois processos.

3. **Faltava `timeout`, e isso explicou uma suíte que "nunca terminava".**
   Medido: **4min26 decorridos com 13 segundos de CPU** — 97% parada — e **12
   conexões ao Google abertas e penduradas**, nenhuma com erro. O
   `HttpRetryOptions` do ADR-0018 reage a **erro**; socket pendurado é
   **silêncio**. O timeout é o que converte um no outro, e sem ele a
   retentativa nunca dispara. Com 60 s, a suíte passou a fechar em 3min38.

4. **Dois testes meus conferiam prosa, não efeito** — o que a regra `B.5` do
   `TODO.md` proíbe. Um exigia `?` na resposta do cancelamento ambíguo, e numa
   rodada o modelo escreveu *"Por favor, informe qual delas…"*: certo, e sem
   interrogação.

**Duas colisões de passo**, do mesmo tipo que o projeto já havia pago:
`cancelar a reserva {codigo}` casando com `do 302`, e
`o {apartamento} cancela essa reserva` casando com `o morador`. O remédio
registrado — **texto do cenário mais específico, não passo mais esperto** — foi
aplicado nas duas.

### Um ganho que o plano dizia ser impossível

O plano afirmava que os cenários `@estrutura` **não pegariam** a armadilha do
`R1`, porque "uma árvore errada ainda é uma árvore". Com `mode="single_turn"`,
o ADK expõe os `sub_agents` em `tools`, e aí dá para conferir o **tipo** do
embrulho. A asserção que exige `type(tool) is not AgentTool` para os dois
transacionais **pega a armadilha** — em menos de um segundo e sem chave de API.
Verificado por sabotagem.

### Uma medição que contradisse um spike

A `rotas/D-04` previu que mensagem nova com pendência aberta custaria "pendência
duplicada". Medido contra o Gemini: **a mensagem não é respondida** — o modelo
reemite a chamada pendente e o ADK descarta o ramo novo. A decisão continua
válida (a condição do enunciado se mantém: nada executa), mas o custo registrado
estava incompleto. Anotado no spike, com o rastro de events.

## Validação

- [x] Revisado e aprovado — 2026-11-08. O usuário delegou as decisões que faltavam ("pode tomar as decisões, nada é crítico"); a `rotas/D-03` foi fechada como **A no código, B num teste** antes de validar.
