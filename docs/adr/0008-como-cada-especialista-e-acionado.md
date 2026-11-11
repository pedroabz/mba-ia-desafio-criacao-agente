# ADR-0008 — Reservas e Visitantes são `sub_agents` em `single_turn`; Regulamento é `AgentTool`

**Status:** aceito
**Data:** 2026-11-08
**Origem:** [`docs/spike-1.2-fronteiras-agentes.md`](../spike-1.2-fronteiras-agentes.md) → topologia derivada das restrições `F-1`/`F-2` + `fronteiras/D-03`
**Invariantes e garantias afetados:** Garantia 1 (confirmação), Garantia 4 (isolamento do regulamento), `I-05`
**Relacionado:** ADR-0007 (define quais especialistas existem)

> Topologia e modo foram registrados juntos porque respondem à **mesma pergunta** — "como o principal aciona cada especialista?" — e a segunda só existe dentro da primeira: `mode` é configuração de `sub_agents`, e não se aplica a `AgentTool`. Separados, nenhum dos dois se lê inteiro.

## Contexto

O Google ADK oferece dois caminhos para um agente principal acionar outro: embrulhá-lo como ferramenta (**`AgentTool`**) ou declará-lo subordinado (**`sub_agents`**, alcançado por transferência de controle). A diferença entre eles não é estilística — ela decide duas garantias do enunciado em direções opostas.

**`AgentTool` executa o agente numa sessão aninhada, que é descartada ao fim.** Só a resposta final volta. Isso foi medido: um especialista que recupera um trecho marcado do regulamento e responde com uma frase curta deixa o histórico da sessão com 7.493 caracteres e **sem** o trecho. O mesmo especialista como `sub_agents` deixa 14.579 caracteres e **com** o trecho, além das chamadas de ferramenta internas.

A mesma sessão descartada que isola o contexto também **destrói a confirmação de ferramenta**. O spike R1 verificou: um agente embrulhado em `AgentTool` que pausa esperando aprovação do morador nunca retoma — a pendência jamais chega à API, e a ação não executa. Sem erro nenhum, que é o que torna a falha cara.

Isso produziu duas restrições que se aplicam a agentes diferentes: **`F-1`** — todo agente com ferramenta de confirmação precisa ser `sub_agents`; **`F-2`** — todo agente que consulte textos longos deve ser `AgentTool`, se não tiver confirmação.

Dentro de `sub_agents` restava uma escolha livre: o ADK oferece os modos `chat`, `task` e `single_turn`, e o spike R1 verificou que **`chat` e `single_turn` retomam a confirmação corretamente**, inclusive após reinício do processo. A restrição não decide entre eles.

## Decisão

| Especialista | Acionamento | Determinado por |
|---|---|---|
| **Reservas** | `sub_agents`, `mode="single_turn"` | `F-1` — tem `criar_reserva`, que confirma quando a área tem taxa |
| **Visitantes** | `sub_agents`, `mode="single_turn"` | `F-1` — tem `autorizar_visitante`, que confirma sempre |
| **Regulamento** | `AgentTool` | `F-2` — consulta textos longos e não tem ferramenta de confirmação |

A topologia **não é escolha**: cada especialista recebe o único mecanismo compatível com a sua restrição. O que foi escolhido é o **modo**: `single_turn`, de forma que o especialista cumpra a tarefa e devolva o controle ao principal, em vez de permanecer ativo nos turnos seguintes.

## Alternativas consideradas

- **Todos os especialistas como `AgentTool`.** Isolaria contexto em todos e daria uma arquitetura uniforme. Eliminada por medição, não por preferência: Reservas e Visitantes têm ferramentas de confirmação, e `AgentTool` as quebra em silêncio (`F-1`).
- **Todos como `sub_agents`.** Preservaria a confirmação em todos. Rejeitada para o Regulamento: foi medido que o trecho consultado entra no histórico da sessão e passa a acompanhar todas as mensagens seguintes, que é exatamente o custo que a Garantia 4 existe para evitar.
- **`mode="chat"` nos especialistas transacionais.** Gasta menos chamadas ao modelo, porque o turno não volta ao principal para fechar — relevante, já que estourar quota do Gemini vira erro de servidor. Rejeitada porque, em `chat`, o especialista permanece ativo e a volta ao principal depende de **o modelo lembrar de transferir**. Com três especialistas, uma pergunta sobre regulamento feita logo após uma reserva chegaria ao agente de Reservas. `single_turn` torna o retorno estrutural em vez de comportamental.

## Consequências

**O que fica mais fácil:** o roteamento é decidido a cada turno por quem tem visão das três opções. O **trecho recuperado** do regulamento e a **chamada de ferramenta** que o buscou não entram na sessão principal — ficam na sessão aninhada, que é descartada.

> **Correção de 2026-11-08, vinda do [spike 1.4](../spike-1.4-estrategia-regulamento.md).** A redação original desta seção dizia que "o texto do regulamento nunca entra na sessão" e que a Garantia 4 valeria "por construção". **Isso era impreciso e otimista demais.** O `AgentTool` devolve ao principal o **texto final do especialista** (`agent_tool.py:508-525`), e esse retorno vira um evento `function_response` na sessão principal. Ou seja: se o especialista citar o capítulo literalmente na resposta, a citação entra na sessão.
>
> O isolamento que esta decisão garante é dos **eventos internos**, não da resposta. A Garantia 4 depende, além da topologia, de uma **política de citação** — que o especialista responda em prosa curta em vez de transcrever o trecho. Isso virou decisão própria (`D-05` do spike 1.4).
>
> A medição do spike 1.2 não detectou o problema porque o especialista roteirizado já respondia com uma frase curta, sem repetir o marcador. A topologia estava sendo medida; a política de citação estava sendo pressuposta.
>
> A decisão deste ADR **não muda** — `AgentTool` continua sendo o mecanismo certo para o Regulamento, e continua sendo o único que impede o trecho recuperado de acumular. O que muda é a extensão da garantia que ele oferece sozinho.

**O que fica mais difícil, ou passa a custar atenção:** cada turno custa uma chamada a mais ao modelo, porque o principal fecha o turno depois do especialista. E o principal **não enxerga** o que o especialista fez — em `single_turn` o trabalho roda num sub-branch. Durante o spike R1 isso produziu um laço infinito num harness de teste, porque o principal não via que a tarefa já tinha sido executada e re-delegava. Instrução e critério de parada precisam levar isso em conta.

**Risco aceito:** o custo em chamadas ao modelo. `chat` seria mais barato, e o enunciado alerta explicitamente sobre volume de chamadas, com o passo 14 do avaliador disparando duas aprovações simultâneas. Aceita-se pagar por previsibilidade de roteamento, coerente com o tema do desafio — *o modelo decide o caminho, o código decide o que é permitido*. Se quota se mostrar o gargalo real, a troca para `chat` é de uma linha por agente, e os cenários abaixo continuam valendo.

> **Anotação de 2026-11-08, vinda do [spike 2.4](../spike-2.4-modelos-gemini.md).
> O risco aceito acima agora tem número, e ele é medido.** Este ADR dizia "cada
> turno custa uma chamada a mais" sem quantificar. O harness contou, com um
> `BaseLlm` roteirizado: um turno encaminhado a um especialista que usa uma
> ferramenta custa **4 chamadas** ao modelo em `single_turn` (principal 2 +
> especialista 2) contra **3** em `chat` (principal 1 + especialista 2). Cada
> ferramenta adicional no mesmo turno soma 1 — um turno com duas ferramentas
> custou 5.
>
> É **uma chamada em quatro**, ou 25% por turno encaminhado. Com ~18
> requisições que invocam o modelo no roteiro do avaliador, isso é a diferença
> entre ~72 e ~54 chamadas.
>
> **A decisão não muda.** O que muda é o tamanho do que foi aceito — e a
> válvula fica registrada com preço conhecido: trocar para `chat` recupera um
> quarto das chamadas dos turnos transacionais e custa a garantia de roteamento
> que este ADR comprou. Ver também o [ADR-0017](0017-um-modelo-flash-lite-nos-quatro-agentes.md),
> que escolheu o modelo **sabendo** desse fator 4: é ele que transforma
> "dezenas de chamadas" em 70–85, e é por isso que a família Flash, com 20
> requisições por dia, está proibida.

## Verificação

| Cenário | Protege | Tipo |
|---|---|---|
| Consultar o regulamento não deixa o trecho no histórico da sessão | Garantia 4, `I-05` | **regressão** — falha se o Regulamento virar `sub_agents` |
| Reservar área com taxa produz confirmação pendente na API | Garantia 1, `F-1` | **regressão** — falha se Reservas virar `AgentTool` |
| Autorizar visitante produz confirmação pendente na API | Garantia 1, `F-1` | **regressão** — falha se Visitantes virar `AgentTool` |
| Depois de um pedido de reserva, uma dúvida de regulamento é atendida | `single_turn` devolvendo o controle | positivo |

Arquivo: `tests/features/agentes.feature`

## Onde isso vive no código

| O quê | Onde |
|---|---|
| `sub_agents` + `mode="single_turn"` | `app/agentes/especialistas.py` → Reservas e Visitantes |
| `AgentTool` | `app/agentes/principal.py` → `tools=[AgentTool(agent=regulamento)]` |

⚠️ **Descoberta da implementação, e ela mudou o que dá para verificar barato.**
Com `mode="single_turn"`, o ADK **converte os `sub_agents` em ferramentas**:
`principal.tools` traz três itens, não um — um `AgentTool` e dois
`_SingleTurnAgentTool`. Isso confirma o que o spike 2.4 mediu (em `single_turn`
o especialista é exposto como função com o nome do agente, não como
`transfer_to_agent`).

A consequência útil: dá para conferir o **tipo** do embrulho de cada
especialista, e com isso a armadilha do `R1` passou a ser pega por inspeção de
árvore — em menos de um segundo e **sem chave de API**. O plano 4 supunha que
só um cenário `@conversa` pegaria. Verificado por sabotagem.

Verificado por `tests/features/agentes.feature` (`@estrutura` e `@conversa`).
