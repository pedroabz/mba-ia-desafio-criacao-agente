# ADR-0007 — O assistente tem três especialistas: Reservas, Visitantes e Regulamento

**Status:** aceito
**Data:** 2026-11-08
**Origem:** [`docs/spike-1.2-fronteiras-agentes.md`](../spike-1.2-fronteiras-agentes.md) → `fronteiras/D-01`
**Invariantes e garantias afetados:** Garantia 4 (isolamento do regulamento); requisito 1 do enunciado (um principal, no mínimo dois especialistas)
**Relacionado:** ADR-0008 (como cada um é acionado), ADR-0009 (o principal não tem ferramentas de domínio)

## Contexto

O Residencial Aurora é um assistente de condomínio construído com Google ADK. O enunciado exige uma arquitetura específica: **um agente principal que distribui o trabalho entre especialistas**, no mínimo dois — e cobra, no README entregue, a justificativa de quantos existem e do que cada um faz.

O domínio tem sete operações: consultar disponibilidade de área, listar as próprias reservas, criar reserva, cancelar reserva, listar os próprios visitantes, autorizar a entrada de um visitante, e consultar o regulamento interno.

A investigação avaliou cinco critérios de corte e rejeitou três por não serem computáveis ou por partirem uma operação ao meio: corte por confirmação (a taxa da área só é conhecida *depois* de consultar, então não dá para rotear antes), corte por leitura × escrita (consultar disponibilidade precede imediatamente a gravação), e o corte pelo isolamento que o Regulamento já tem.

Sobrou uma pergunta genuína: **reservas e visitantes ficam no mesmo especialista ou em dois?** As duas famílias compartilham tudo que é mecânico — o apartamento vem do state da sessão, as ações sensíveis passam pela mesma máquina de confirmação, e gravam no mesmo banco.

## Decisão

**Três especialistas**, separados por domínio:

| Especialista | Operações |
|---|---|
| **Reservas** | consultar disponibilidade, listar as próprias reservas, criar reserva, cancelar reserva |
| **Visitantes** | listar os próprios visitantes, autorizar a entrada de um visitante |
| **Regulamento** | consultar o regulamento interno |

O critério é **responsabilidade de domínio, não economia de chamadas**: autorizar a entrada de alguém no prédio e reservar o salão de festas são assuntos distintos, que não se cruzam em nenhuma operação. Agentes que não compartilham assunto não compartilham instrução.

## Alternativas consideradas

- **Dois especialistas — um "Transacional" com as seis ferramentas de reserva e visitante, mais o Regulamento.** Era a recomendação do spike, por dois argumentos: nenhuma fronteira *exige* o corte (mesma amarração à sessão, mesma confirmação, mesmo storage), e cada especialista alcançado por transferência custa o prompt inteiro reenviado sem cache — o próprio ADK avisa disso (`runners.py:491-497`), e o avaliador faz dezenas de chamadas ao modelo. Rejeitada por clareza de responsabilidade: misturar dois assuntos numa instrução só economiza chamadas às custas de um agente que precisa saber de tudo.

## Consequências

**O que fica mais fácil:** cada instrução cobre um assunto só, e fica mais curta. Quando o modelo erra a seleção de ferramenta, o diagnóstico é mais direto — o agente errado é visível no histórico de eventos. E a separação se defende sozinha na seção Arquitetura do README: é por domínio, não por conveniência técnica.

**O que fica mais difícil, ou passa a custar atenção:** mais um agente alcançado por transferência, e portanto mais um ponto onde o prompt inteiro é reenviado sem cache. Numa conversa que trate de reserva **e** de visitante, são duas transferências em vez de uma — e o enunciado alerta que estourar quota do Gemini vira erro de servidor, com o passo 14 do avaliador disparando duas aprovações simultâneas.

**Risco aceito — e este é o mais relevante:** **dois especialistas passam a ter ferramentas que exigem confirmação**, não um. `criar_reserva` confirma quando a área tem taxa; `autorizar_visitante` confirma sempre. A retomada da confirmação roteia para o agente que a pediu, e o spike R1 verificou esse mecanismo com **um** agente que confirma. Com dois, o roteador precisa acertar entre eles — comportamento que **não foi medido**. É a superfície de risco que esta decisão amplia, e o motivo pelo qual a recomendação era o caminho oposto. Mitigação: testar a retomada nos dois especialistas antes de considerar a Fase 4 concluída.

## Verificação

| Cenário | Protege | Tipo |
|---|---|---|
| Cada especialista tem apenas as ferramentas do seu domínio | a decisão deste ADR | positivo |
| A confirmação de reserva retoma no especialista de Reservas | o risco aceito acima | **regressão** — falha se a retomada rotear para o agente errado |
| A confirmação de visitante retoma no especialista de Visitantes | o risco aceito acima | **regressão** |

Arquivo: `tests/features/agentes.feature`

## Onde isso vive no código

| O quê | Onde |
|---|---|
| Os três especialistas | `app/agentes/especialistas.py` |
| A montagem da árvore | `app/agentes/principal.py` → `criar_agente_principal` |
| Reservas: 5 ferramentas | `app/agentes/ferramentas/reservas.py` |
| Visitantes: 2 ferramentas | `app/agentes/ferramentas/visitantes.py` |
| Regulamento: 1 ferramenta | `app/agentes/ferramentas/regulamento.py` |

**O risco aceito deste ADR foi exercido, e passou.** Ele registrou que, com
três especialistas, passam a existir **dois** agentes com ferramenta de
confirmação — e o spike R1 havia medido a retomada com **um** só. Os cenários
`A confirmação de reserva retoma no especialista de Reservas` e o par de
Visitantes são a primeira vez que o caso de dois é exercido; os dois estão
verdes, e o passo 11 do `scripts/validar.py` confirma pelo fluxo completo.

Verificado por 4 cenários `@estrutura` em `tests/features/agentes.feature`.
