# ADR-0009 — O agente principal roteia e não tem nenhuma ferramenta que toque dados do condomínio

**Status:** aceito
**Data:** 2026-11-08
**Origem:** [`docs/spike-1.2-fronteiras-agentes.md`](../spike-1.2-fronteiras-agentes.md) → `fronteiras/D-02`
**Invariantes e garantias afetados:** `I-02`, `I-06`; Garantia 2; Garantia 4
**Relacionado:** ADR-0007 (quais especialistas existem), ADR-0008 (como são acionados)

## Contexto

No Residencial Aurora, o morador conversa com um agente principal que distribui o trabalho entre especialistas. O enunciado exige que reservas e visitantes sejam "lidos e gravados por tools", e que o apartamento que essas ferramentas usam venha **da sessão**, nunca de um valor que o modelo escolha sem validação. O passo 15 do roteiro do avaliador confere isso **por leitura de código**: ele procura por qualquer ferramenta que aceite um apartamento vindo do modelo.

O enunciado não diz de qual agente essas ferramentas são. E existe uma tentação concreta: dar ao principal uma ferramenta de leitura — *"quais são minhas reservas?"* — para responder sem pagar uma transferência de controle, que no ADK custa o prompt inteiro reenviado sem cache.

Há ainda um detalhe que torna a formulação ingênua ("o principal não tem ferramentas") falsa na implementação: o especialista de Regulamento é acionado como `AgentTool` (ADR-0008), ou seja, **é** uma ferramenta na lista do principal.

## Decisão

O agente principal **não tem nenhuma ferramenta que leia ou grave dados do condomínio**. Ele roteia.

A formulação precisa importa, porque ele tem ferramentas:

- **tem** o especialista de Regulamento, que é `AgentTool` — mas essa ferramenta consulta um documento, não o banco;
- **tem** `transfer_to_agent`, que o ADK injeta por haver `sub_agents`;
- **não tem** nenhuma ferramenta que toque reserva, autorização de entrada ou o apartamento da sessão.

Reservas e visitantes são lidos e gravados exclusivamente pelas ferramentas dos especialistas de Reservas e Visitantes.

E, por exigência direta da Garantia 4: **o principal não recebe o regulamento nas instruções.** Isso não é escolha, é requisito conferido no passo 15.

## Alternativas consideradas

- **Dar ao principal as ferramentas de leitura**, deixando só a escrita com os especialistas. Perguntas como "quais são minhas reservas?" responderiam sem transferência, economizando chamadas ao modelo num fluxo que já faz dezenas. Rejeitada por dois motivos: duplicaria a superfície onde o invariante do apartamento (`I-02`) precisa valer, justamente o invariante que o avaliador fiscaliza lendo código; e reintroduziria pela porta dos fundos o corte "leitura × escrita", que a análise de fronteira já havia rejeitado porque consultar disponibilidade e gravar a reserva são uma operação só.

## Consequências

**O que fica mais fácil:** existe **um lugar por domínio** que lê o apartamento da sessão e toca os dados. Conferir que nenhuma ferramenta aceita apartamento escolhido pelo modelo passa a ser uma inspeção localizada — e é exatamente essa inspeção que o passo 15 faz. O principal fica com uma instrução curta, sobre roteamento, sem regra de negócio.

**O que fica mais difícil, ou passa a custar atenção:** toda pergunta sobre dados do condomínio paga uma transferência, inclusive leituras simples. Com `single_turn` (ADR-0008), isso significa principal → especialista → principal a cada turno.

**Risco aceito:** o custo em chamadas ao modelo das leituras. Aceito porque a alternativa troca economia por espalhar o invariante mais fiscalizado do desafio — e porque o enunciado penaliza explicitamente garantias que dependem de disciplina em vez de estrutura.

## Verificação

| Cenário | Protege | Tipo |
|---|---|---|
| O agente principal não tem ferramenta que toque o banco | a decisão deste ADR | **regressão** — falha se alguém adicionar uma ferramenta de leitura ao principal |
| As instruções do agente principal não contêm o regulamento | Garantia 4, passo 15 | **regressão** |
| Nenhuma ferramenta aceita apartamento vindo do modelo | `I-02`, Garantia 2, passo 15 | **regressão** |

Arquivo: `tests/features/agentes.feature`

## Onde isso vive no código

| O quê | Onde |
|---|---|
| O agente principal | `app/agentes/principal.py` → `criar_agente_principal` |
| As instruções dele | `app/agentes/principal.py` → `INSTRUCAO_PRINCIPAL` |
| `tools` só com especialistas | nenhuma função de domínio é passada ao principal |

As duas proibições deste ADR são verificadas por inspeção, que é a mesma coisa
que o **passo 15** do avaliador faz lendo o código — a diferença é que aqui
falha sozinho:

- `O agente principal não tem ferramenta que toque o banco` confere que toda
  ferramenta dele embrulha um agente, nenhuma é função própria;
- `As instruções do agente principal não contêm o regulamento` procura
  marcadores que só existem no documento (`Art. 1º`, `Parágrafo único`,
  `coleira refletiva`) e qualquer linha literal com mais de 80 caracteres.

⚠️ **A instrução do principal tem dois parágrafos de ROTEAMENTO, não de
garantia**, e a distinção está comentada no código. Eles existem porque, com
uma confirmação aberta no histórico, o principal chamava dois especialistas de
uma vez e a pergunta do morador ficava sem resposta. Nenhuma garantia dependia
disso — nada executava — e por isso o lugar deles é a instrução.

Verificado por 2 cenários `@estrutura` em `tests/features/agentes.feature`.
