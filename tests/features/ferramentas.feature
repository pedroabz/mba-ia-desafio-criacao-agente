# language: pt
# Origem: docs/spike-1.3-superficie-de-tools.md (Fase 1.3)
# ADRs: 0010 (data como string) · 0011 (recusa não vira 500) · 0012 (duas
#       ferramentas de cancelamento) · 0013 (portão de confirmação)
#
# @pendente = ainda não implementado, FALHA de propósito. Nunca apagar.

Funcionalidade: As ferramentas do assistente

  Contexto:
    Dado o condomínio com os dados iniciais carregados

  # ADR-0010
  @ferramenta
  Cenário: Data em formato válido grava a reserva no dia certo
    Quando a ferramenta de reserva é chamada com a quadra em "2030-04-06"
    Então a reserva é criada para 2030-04-06

  # REGRESSÃO · ADR-0010 · falha se alguém trocar `data: str` por `data: date`
  # achando que o ADK converte. Ele não converte: FUNCTION_TOOL_ARG_VALIDATION
  # é default_on=False, e a função passa a receber string onde espera date.
  @ferramenta
  Cenário: Data malformada vira recusa, não erro
    Quando a ferramenta de reserva é chamada com a quadra em "06/04/2030"
    Então a chamada devolve uma recusa legível
    E nenhuma exceção escapa da ferramenta

  # REGRESSÃO · ADR-0011 · verificado que exceção escapando derruba
  # runner.run_async e a API responde 500 — o que a Garantia 5 proíbe.
  @ferramenta
  Cenário: Recusa de negócio não escapa como exceção
    Dado que o 101 não tem reserva da churrasqueira em 2030-07-01
    Quando a ferramenta de cancelamento por área e data é chamada
    Então a chamada devolve uma recusa legível
    E nenhuma exceção escapa da ferramenta

  # ADR-0011 · o `except` local existe onde a exceção carrega dado aproveitável
  @ferramenta
  Cenário: Área inexistente informa que não é reservável
    Quando a ferramenta de reserva é chamada com a área "piscina"
    Então a chamada devolve uma recusa dizendo que a área não é reservável
    E a recusa carrega as áreas que podem ser reservadas

  # BUG CONFIRMADO em código existente: data_esta_livre não valida a área
  # (repositorio_sqlite.py:94-100) e responde "livre" para a piscina.
  # A lista de áreas válidas vai para o MODELO, não para a resposta ao morador.
  @ferramenta
  Cenário: Consultar disponibilidade de área inexistente não responde livre
    Quando a ferramenta de disponibilidade é chamada com a área "piscina"
    Então a chamada não responde que a data está livre
    E devolve uma recusa dizendo que a área não é reservável

  # REGRESSÃO · I-06 · passo 10 · a projeção do retorno é o único mecanismo
  @ferramenta
  Cenário: Consultar data ocupada não revela o dono
    Dado que o 302 tem o salão reservado em 2030-03-16
    Quando a ferramenta de disponibilidade é chamada com o salão em "2030-03-16"
    Então o retorno diz apenas que a data está ocupada
    E o retorno não contém o código da reserva nem o número do apartamento dono

  # ADR-0012
  @ferramenta
  Cenário: Cancelar citando área e data cancela a reserva certa
    Dado que o 101 tem a quadra reservada em 2030-04-06
    Quando a ferramenta de cancelamento por área e data é chamada com a quadra em "2030-04-06"
    Então a quadra em 2030-04-06 some das reservas do 101
    E o retorno identifica a área e a data canceladas

  # ADR-0012
  @ferramenta
  Cenário: Cancelar citando o código cancela a reserva certa
    Dado que o 101 tem a reserva RSV-1377 da quadra em 2030-03-09
    Quando a ferramenta de cancelamento por código é chamada com "RSV-1377"
    Então a RSV-1377 some das reservas do 101

  # REGRESSÃO · ADR-0012 · ADR-0004 · I-02 · I-06
  @ferramenta
  Cenário: Cancelar código de outro apartamento não altera nada nem confirma a existência
    Dado que a reserva RSV-4821 pertence ao 302
    Quando a ferramenta de cancelamento por código é chamada com "RSV-4821" numa sessão do 101
    Então nenhuma reserva do 302 é alterada
    E o retorno não confirma nem nega a existência dessa reserva

  # I-02 · o apartamento vem do state da sessão, nunca de parâmetro
  @ferramenta
  Cenário: Listar as próprias reservas devolve só as do apartamento da sessão
    Dado uma sessão do 101
    Quando a ferramenta de listar reservas é chamada
    Então o retorno traz a reserva da quadra do 101
    E não traz nenhuma reserva do 302

  # REGRESSÃO · ADR-0001 · o filtro ativa = 1 é disciplina de código, sem
  # mecanismo que o force. Esquecer num lugar vaza cancelada para a conversa.
  @ferramenta
  Cenário: Listar as próprias reservas não traz reserva cancelada
    Dado uma sessão do 101
    E que o 101 cancelou a reserva da quadra em 2030-03-09
    Quando a ferramenta de listar reservas é chamada
    Então o retorno não traz essa reserva

  # REGRESSÃO · achado da 1.3: retorno não-dict é embrulhado em {"result": …}
  # pelo ADK (_caller.py:310), e é isso que aparece no GET /eventos que o
  # avaliador lê no passo 12. Falha se a ferramenta devolver lista crua.
  @ferramenta
  Cenário: As listagens devolvem um dicionário nomeado, não uma lista crua
    Dado uma sessão do 101
    Quando a ferramenta de listar reservas é chamada
    Então o retorno é um dicionário com chave nomeada
    E a chave não é "result"

  # I-02
  @ferramenta
  Cenário: Listar os próprios visitantes devolve só os do apartamento da sessão
    Dado uma sessão do 302
    Quando a ferramenta de listar visitantes é chamada
    Então a lista de visitantes traz Marina Duarte
    E não traz visitante de outro apartamento

  # ADR-0005 · a recusa vem do banco, não de checagem prévia
  @ferramenta
  Cenário: Autorizar visitante grava e recusa a duplicata
    Dado uma sessão do 101
    Quando a ferramenta de autorizar visitante é chamada com Joana Ribeiro em "2030-04-21"
    Então a autorização é criada
    E chamar de novo com os mesmos dados devolve uma recusa legível
    E o 101 continua com exatamente uma autorização para Joana Ribeiro

  # ADR-0013 · Garantia 1 · passo 7
  @ferramenta
  Cenário: Reservar área com taxa aciona o portão de confirmação
    Quando o portão de confirmação é consultado para o salão de festas
    Então ele decide que a ação exige confirmação

  # REGRESSÃO · ADR-0013 · Garantia 1 · passo 6 · falha se o portão passar a
  # confirmar sempre, ou se a leitura da taxa degradar para "não confirma".
  @ferramenta
  Cenário: Reservar área sem taxa não aciona o portão
    Quando o portão de confirmação é consultado para a quadra
    Então ele decide que a ação não exige confirmação

  # ADR-0013 · Garantia 1 · passo 11
  @ferramenta
  Cenário: Autorizar visitante sempre aciona o portão
    Quando o portão de confirmação é consultado para uma autorização de entrada
    Então ele decide que a ação exige confirmação

  # REGRESSÃO · ADR-0013 · G-2 · passo 10 · é a fresta que o spike 1.6 achou:
  # o argumento inventado pelo modelo fica nos args da chamada original, e
  # chegaria à resposta da API se ela repassasse sem filtrar.
  @api
  Cenário: Argumento inventado pelo modelo não aparece nos detalhes da pendência
    Dado uma chamada de reserva cujos argumentos incluem um apartamento inventado
    Quando a API projeta a confirmação pendente
    Então os detalhes contêm apenas a área e a data
    E os detalhes não contêm nenhum número de apartamento
