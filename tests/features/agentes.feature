# language: pt
# Origem: docs/spike-1.2-fronteiras-agentes.md (Fase 1.2)
# ADRs: 0007 (três especialistas) · 0008 (como cada um é acionado) · 0009 (o
#       principal não tem ferramentas de domínio)
#
# TODOS pendentes: os agentes só existem na Fase 4. Falham de propósito —
# cenário pulado é invisível, e invisível é perdido. Nunca apagar.

Funcionalidade: Fronteiras entre os agentes

  # ADR-0007 — a separação por domínio precisa ser verificável, não só
  # declarada no README. Falha se alguém juntar os dois transacionais de novo.
  @estrutura
  Cenário: Cada especialista tem apenas as ferramentas do seu domínio
    Dado a árvore de agentes montada
    Então o especialista de Reservas não tem ferramenta de visitante
    E o especialista de Visitantes não tem ferramenta de reserva
    E o especialista de Regulamento não tem ferramenta que toque o banco

  # REGRESSÃO · ADR-0009 · I-02 · passo 15 do avaliador, que confere isso
  # lendo o código. Falha no dia em que alguém der uma ferramenta de leitura
  # ao principal "só para economizar uma transferência".
  @estrutura
  Cenário: O agente principal não tem ferramenta que toque o banco
    Dado a árvore de agentes montada
    Então o agente principal não tem nenhuma ferramenta de domínio
    E as ferramentas que ele tem são o especialista de Regulamento e a transferência

  # REGRESSÃO · Garantia 4 · passo 15
  @estrutura
  Cenário: As instruções do agente principal não contêm o regulamento
    Dado a árvore de agentes montada
    Quando as instruções do agente principal são inspecionadas
    Então elas não contêm texto do regulamento

  # REGRESSÃO · I-02 · Garantia 2 · é a inspeção que o passo 15 faz.
  @estrutura
  Cenário: Nenhuma ferramenta aceita apartamento escolhido pelo modelo
    Dado a árvore de agentes montada
    Então nenhuma ferramenta declara um parâmetro de apartamento

  # REGRESSÃO · ADR-0008 · F-2 · Garantia 4 · I-05
  # Falha se o Regulamento virar sub_agents: o trecho consultado passaria a
  # entrar na sessão e a acompanhar todas as mensagens seguintes.
  @conversa
  Cenário: Consultar o regulamento não deixa o trecho no histórico da sessão
    Dado uma sessão do 101
    Quando o morador pergunta até que horas a piscina funciona aos domingos
    Então a resposta traz o horário de fechamento que consta no regulamento
    E os eventos da sessão não contêm o texto do capítulo consultado

  # REGRESSÃO · ADR-0008 · F-1 · Garantia 1
  # Falha se Reservas virar AgentTool: a sessão aninhada é descartada e a
  # pendência nunca chega à API — sem erro nenhum.
  @conversa
  Cenário: Reservar área com taxa produz confirmação pendente
    Dado uma sessão do 101
    Quando o morador pede o salão de festas para 2030-04-20
    Então a resposta traz uma confirmação pendente com a área e a data

  # REGRESSÃO · ADR-0008 · F-1 · mesma falha, no outro especialista.
  @conversa
  Cenário: Autorizar visitante produz confirmação pendente
    Dado uma sessão do 101
    Quando o morador pede para liberar a entrada de Joana Ribeiro em 2030-04-21
    Então a resposta traz uma confirmação pendente com o nome e a data

  # ⚠️ REGRESSÃO · I-04 · Garantia 1 · ADR-0007, risco aceito.
  # ESTE É O CENÁRIO QUE COBRE O I-04 — "cobrança ou acesso só após
  # confirmação". Ele é o único invariante dos seis cujo mecanismo é o
  # `require_confirmation` do ADK mais a rota de confirmações, e por isso só
  # fica verificável quando as duas pontas existem.
  # Com DOIS especialistas que confirmam, a retomada precisa rotear para o
  # certo. O spike R1 mediu com um só; isto aqui é a primeira vez que o caso
  # de dois é exercido.
  @conversa
  Cenário: A confirmação de reserva retoma no especialista de Reservas
    Dado uma confirmação pendente de reserva na sessão do 101
    Quando o morador aprova pela rota de confirmações
    Então a reserva é criada exatamente uma vez

  # REGRESSÃO · ADR-0007, risco aceito · o par do cenário acima.
  @conversa
  Cenário: A confirmação de visitante retoma no especialista de Visitantes
    Dado uma confirmação pendente de visitante na sessão do 101
    Quando o morador aprova pela rota de confirmações
    Então a autorização é criada exatamente uma vez

  # ADR-0008 · single_turn devolve o controle ao principal, então a pergunta
  # seguinte é roteada por quem enxerga os três especialistas. Em mode=chat
  # isso dependeria de o modelo lembrar de transferir de volta.
  @conversa
  Cenário: Depois de um pedido de reserva, uma dúvida de regulamento é atendida
    Dado uma sessão do 101
    E que o morador acabou de pedir uma reserva
    Quando ele pergunta até que horas a piscina funciona aos domingos
    Então a resposta traz o horário de fechamento

  # ⚠️ REGRESSÃO DE ROTEAMENTO · o spike 1.4 mediu que "Reserve o salão de
  # festas para 2030-04-20" pontua 0,568 no Cap. VI do regulamento — dez
  # vezes mais que uma pergunta claramente fora de escopo, e acima de
  # qualquer corte defensável. Nenhum corte do recuperador separa dúvida de
  # pedido: a defesa é o principal rotear certo.
  # Se este cenário falhar, o morador recebe as REGRAS DE USO do salão em vez
  # de uma reserva — e a reserva nunca acontece, em silêncio.
  @conversa
  Cenário: Um pedido de reserva vai para Reservas, não para Regulamento
    Dado uma sessão do 101
    Quando o morador escreve "Reserve o salão de festas para 2030-04-20"
    Então a ferramenta de reserva foi chamada
    E nenhuma ferramenta do especialista de Regulamento foi chamada

  # Variação do mesmo risco, pelo lado oposto: uma dúvida não pode virar ação.
  @conversa
  Cenário: Uma dúvida sobre o salão não cria reserva
    Dado uma sessão do 101
    Quando o morador pergunta "posso fixar enfeites na parede do salão?"
    Então nenhuma reserva é criada
    E nenhuma confirmação pendente é gerada

  # Fora de escopo do condomínio. O assistente não deve inventar resposta nem
  # devolver capítulo arbitrário do regulamento (o recuperador tem corte, mas
  # o roteamento vem antes).
  @conversa
  Cenário: Pergunta fora do domínio do condomínio não aciona ferramenta nenhuma
    Dado uma sessão do 101
    Quando o morador pergunta "quanto custa o bitcoin hoje?"
    Então nenhuma ferramenta de domínio foi chamada
    E a resposta não cita nenhum capítulo do regulamento

  # Saudação: não é pedido nem dúvida. Medido: "oi, tudo bem?" pontua 0,050
  # no Cap. V (Academia) — baixo, mas não nulo.
  @conversa
  Cenário: Saudação não aciona ferramenta nenhuma
    Dado uma sessão do 101
    Quando o morador escreve "oi, tudo bem?"
    Então nenhuma ferramenta foi chamada
