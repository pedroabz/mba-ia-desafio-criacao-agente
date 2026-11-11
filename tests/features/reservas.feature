# language: pt
# Origem: docs/spike-dominio-invariantes.md (Fase 1.1)
# ADRs: 0001 (soft delete) · 0003 (validação de área) · 0004 (contrato de cancelamento)
#
# Toda etiqueta @pendente marca cenário ainda não implementado. Ele FALHA na
# suíte de propósito: cenário pulado é invisível, e invisível é perdido.
# Implementar = remover @pendente e fazer passar. Nunca apagar.

Funcionalidade: Reservas de áreas comuns

  Contexto:
    Dado o condomínio com os dados iniciais carregados

  # I-01 · regra de negócio 1
  @storage
  Cenário: Exclusividade da área por data
    Dado que o 302 tem o salão reservado em 2030-03-16
    Quando o 101 tenta reservar o salão em 2030-03-16
    Então a reserva não é criada
    E a recusa não revela de quem é a reserva existente

  # I-01 · a exclusividade vale também contra o próprio apartamento, mas aqui
  # a resposta PODE identificar a reserva, porque ela é do próprio morador.
  @storage
  Cenário: Reservar área e data que o próprio apartamento já reservou
    Dado que o 101 tem a quadra reservada em 2030-04-06
    Quando o morador do 101 pede a quadra em 2030-04-06 de novo
    Então nenhuma reserva nova é criada
    E a resposta informa que ele já tem essa reserva
    E o 101 continua com exatamente uma reserva da quadra em 2030-04-06

  # ADR-0001 · I-01
  @storage
  Cenário: Cancelar a própria reserva libera a data
    Dado que o 101 tem a quadra reservada em 2030-04-06
    Quando o 101 cancela essa reserva
    Então a quadra em 2030-04-06 deixa de constar nas reservas do 101
    E a quadra passa a constar como livre em 2030-04-06

  # REGRESSÃO · ADR-0001 · falha se o índice for UNIQUE(area, data) sem a
  # cláusula parcial WHERE ativa = 1 — a data cancelada ficaria bloqueada
  # para sempre, e nenhum teste de reserva comum pegaria isso.
  @storage
  Cenário: Data liberada por cancelamento aceita nova reserva de outro apartamento
    Dado que o 302 tinha o salão reservado em 2030-03-16
    E que essa reserva foi cancelada
    Quando o 101 reserva o salão em 2030-03-16
    Então a reserva do 101 é criada

  # REGRESSÃO · ADR-0001 · I-03 · falha no dia em que alguém "simplificar"
  # o cancelamento para DELETE: o código sumiria do banco e poderia reaparecer.
  @storage
  Cenário: Código nunca se repete, nem o de uma reserva cancelada
    Dado que existiu uma reserva de código C, depois cancelada
    Quando qualquer reserva nova é criada
    Então seu código é diferente de C

  # REGRESSÃO · ADR-0001 · falha se UMA leitura esquecer o filtro ativa = 1.
  # É a falha mais provável desta decisão.
  @storage
  Cenário: Reserva cancelada não aparece nas reservas do morador
    Dado que o 101 tinha a quadra reservada em 2030-04-06
    E que essa reserva foi cancelada
    Quando o morador lista as próprias reservas
    Então a quadra em 2030-04-06 não aparece na lista
    E o código dessa reserva não aparece na resposta

  # ADR-0003
  @conversa
  Cenário: Reservar área que não existe falha
    Dado uma sessão do 101
    Quando o morador pede para reservar a piscina em 2030-05-02
    Então nenhuma reserva é criada
    E a resposta informa quais áreas podem ser reservadas

  # ADR-0004
  @storage
  Cenário: Cancelar citando o código da própria reserva
    Dado que o 101 tem a reserva RSV-1377 da quadra em 2030-03-09
    Quando o morador pede para cancelar a reserva RSV-1377
    Então a reserva RSV-1377 deixa de constar nas reservas do 101
    E a resposta identifica qual reserva foi cancelada

  # REGRESSÃO · ADR-0004 · I-02 · I-06 · falha se a validação de dono sumir,
  # OU se a resposta distinguir "não é seu" de "não existe" — a distinção
  # transformaria a ferramenta num oráculo sobre reservas alheias.
  @storage
  Cenário: Cancelar citando o código de uma reserva de outro apartamento
    Dado uma sessão do 101
    E que a reserva RSV-4821 pertence ao 302
    Quando o morador pede para cancelar a reserva RSV-4821
    Então nada das reservas do 302 é alterado
    E a resposta não confirma nem nega a existência dessa reserva

  # ADR-0004
  @storage
  Cenário: Cancelar reserva que não existe
    Dado que o 101 não tem reserva da churrasqueira em 2030-07-01
    Quando o morador pede para cancelar a churrasqueira em 2030-07-01
    Então nada é alterado
    E a resposta informa que não há essa reserva

  # ADR-0004 · verificar EFEITO, não prosa: a asserção é que nenhuma
  # ferramenta de cancelamento foi chamada, e que houve resposta ao morador.
  @conversa
  Cenário: Pedido de cancelamento ambíguo não executa nada
    Dado que o 101 tem reserva da quadra em 2030-04-06 e do salão em 2030-04-20
    Quando o morador pede "cancela minha reserva", sem dizer qual
    Então nenhuma reserva é cancelada
    E o assistente pergunta qual das duas deve ser cancelada

  # ADR-0004 · sem confirmação prévia, a resposta é a única chance de o
  # morador perceber um engano.
  @conversa
  # ⚠️ A redação destes dois passos é específica de propósito. "o {apartamento}
  # cancela essa reserva" e "que o {apartamento} tem a quadra reservada em
  # {data}" já são passos registrados no conftest, para os cenários @storage —
  # e o primeiro casa com "o morador cancela...", com apartamento="morador".
  # Além da colisão, o Dado do conftest grava pela camada de banco e seria
  # APAGADO pelo `semear` que a fixture da aplicação roda depois.
  # O remédio do projeto é tornar o texto do cenário mais específico.
  Cenário: Cancelamento informa explicitamente o que foi cancelado
    Dado uma sessão do 101 com a quadra reservada em 2030-04-06
    Quando o morador pede o cancelamento dessa reserva pelo chat
    Então a resposta diz qual área e qual data foram canceladas

  # REGRESSÃO · I-06 · Garantia 2, 2ª cláusula · passo 10 do avaliador
  @conversa
  Cenário: Projeção não vaza o dono
    Dado uma sessão do 101
    Quando o morador consulta se o salão está livre em 2030-03-16
    Então a resposta diz apenas que a data está ocupada
    E não contém o código da reserva nem o número do apartamento dono

  # REGRESSÃO · I-02 · Garantia 2, 1ª cláusula · passo 4 do avaliador
  @conversa
  # ⚠️ A redação diz "tenta cancelar", e não "pede para cancelar", porque
  # "pede para cancelar a reserva {codigo}" já é um passo registrado no
  # conftest (cenários @storage) e casa com qualquer sufixo — inclusive
  # "do 302". O cenário ficou vermelho com KeyError por causa disso.
  # O remédio do projeto para colisão de passo é tornar o TEXTO DO CENÁRIO
  # mais específico, nunca o passo mais esperto.
  Cenário: Escopo de escrita
    Dado uma sessão do 101
    Quando o morador tenta cancelar a reserva do apartamento 302
    Então nada do 302 é alterado
    E nem a resposta nem os eventos da sessão contêm o código dessa reserva
