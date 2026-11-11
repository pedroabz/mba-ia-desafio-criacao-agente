# language: pt
# Origem: triagem do spike 1.1 (consolidate-spike) e, nos dois últimos
#         cenários, a revisão do plano 1.4 (os passos P1 e P3 apontavam para
#         cenários que nunca foram escritos)
# ADRs: 0001, 0002, 0014 · Garantia 3 do enunciado (nada se perde no reinício)
#
# Estes cenários nasceram da triagem, não do spike: a consolidação encontrou
# duas fatias de trabalho prontas — ligar o banco na aplicação e os comandos
# de subida/restauração — e nenhuma tinha cenário que a verificasse.
#
# @pendente = ainda não implementado, FALHA de propósito. Nunca apagar.

Funcionalidade: Persistência dos dados do condomínio

  # ADR-0006 — num clone limpo não existe banco nenhum, e o passo 1 do
  # avaliador sobe a API logo depois de restaurar. Subir precisa bastar.
  @api
  Cenário: A aplicação sobe sobre um banco sem schema e o cria
    Dado um banco sem o schema aplicado
    Quando a aplicação é construída
    Então o schema passa a existir
    E as rotas de verificação respondem sem erro

  # REGRESSÃO · ADR-0006 · o DDL é idempotente (IF NOT EXISTS), e é isso que
  # permite dois pontos de entrada criarem estrutura sem conflito. Falha se
  # alguém trocar por "limpar antes de criar".
  @api
  Cenário: A aplicação sobe sobre um schema existente sem apagar dados
    Dado a aplicação ligada ao banco
    E que uma reserva foi criada pela aplicação
    Quando a aplicação é construída de novo sobre o mesmo banco
    Então a reserva continua lá

  # REGRESSÃO · falha no dia em que criar_app() voltar a montar um repositório
  # em memória. Enquanto fosse assim, o que a conversa gravava morria com o
  # processo, e a Garantia 3 caía no passo 13 do avaliador.
  @api
  Cenário: As rotas de verificação leem do banco, não da memória
    Dado a aplicação ligada ao banco
    Quando uma reserva é gravada diretamente no banco
    Então ela aparece em GET /apartamentos/{numero}/reservas

  # REGRESSÃO · Garantia 3 · passo 13 do avaliador: ele reinicia a API SEM
  # restaurar e confere que reservas, cancelamentos e visitantes continuam
  # valendo. Falha no dia em que alguém trocar o repositório por memória.
  @api
  Cenário: O que foi gravado sobrevive ao reinício da aplicação
    Dado a aplicação ligada ao banco
    E que uma reserva foi criada pela aplicação
    Quando a aplicação é construída de novo sobre o mesmo banco
    Então a reserva continua aparecendo nas reservas do apartamento

  # O passo 1 do avaliador roda o comando de restauração num clone limpo e
  # confere que RSV-1377 e Marina Duarte estão lá.
  @storage
  Cenário: A restauração devolve os dados ao estado inicial
    Dado o condomínio com os dados iniciais carregados
    E que uma reserva foi criada e outra cancelada
    Quando a restauração é executada
    Então o apartamento 101 tem a reserva RSV-1377 da quadra em 2030-03-09
    E o apartamento 302 tem Marina Duarte autorizada em 2030-03-16
    E a reserva criada depois do estado inicial não existe mais

  # REGRESSÃO · a restauração mexe no banco, nunca nos arquivos de origem.
  @storage
  Cenário: A restauração não escreve em dados/
    Dado o condomínio com os dados iniciais carregados
    Quando a restauração é executada
    Então os arquivos em dados/ continuam byte-idênticos aos originais

  # ───────────────────────────────────────────────────────────────────────────
  # Os dois cenários abaixo nasceram na REVISÃO do plano 1.4: os passos P1 e P3
  # declaravam estes nomes como critério de pronto e nenhum existia em
  # tests/features/. Passo sem critério de pronto verificável não entra no
  # plano — então o que faltava era o cenário, não o passo.
  # ───────────────────────────────────────────────────────────────────────────

  # ⚠️ REGRESSÃO · ADR-0014, o RISCO ACEITO · é o cenário que AUTORIZA a
  # migração: ele é o P1 do plano 1.4, primeiro de propósito, para falhar
  # barato. A retomada da confirmação foi verificada com SQLite, nunca com
  # Postgres, e o enunciado nomeia o serviço de sessão como um dos fatores que
  # mudaram esse comportamento nos testes do autor.
  # A falha é silenciosa — a rota aceita, nada dá erro, a ação não executa —, e
  # é por isso que a asserção é sobre o EFEITO (executou uma vez), nunca sobre
  # a resposta ter chegado.
  # Marcador: @runner — passa pelo runner do ADK com um LLM roteirizado, como
  # no spike R1, e NÃO precisa de chave de API. Esteve em @conversa por falta
  # de marcador melhor; ver a nota em modelos.feature.
  @runner
  Cenário: A retomada da confirmação funciona com sessão em Postgres
    Dado a aplicação com a sessão do ADK em Postgres
    E uma confirmação pendente criada por outro processo
    Quando o processo é reiniciado e o morador aprova pela rota de confirmações
    Então a reserva criada pelo processo seguinte é exatamente uma

  # ADR-0014, a consequência de depender de serviço externo · é o P3 do plano
  # 1.4. O passo 1 do roteiro roda num CLONE LIMPO: se o docker compose falhar
  # na máquina do avaliador, nada funciona, e o erro precisa dizer o que fazer
  # em vez de empilhar rastro de pilha.
  @api
  Cenário: Subir a aplicação sem o banco no ar falha com mensagem clara
    Dado nenhum Postgres acessível na URL configurada
    Quando a aplicação é construída
    Então a subida falha
    E a mensagem de erro diz qual comando sobe o banco
    E a mensagem não contém rastro de pilha

  # ⚠️ REGRESSÃO · ADR-0014 · o cenário acima cobre `criar_app`; este cobre o
  # COMANDO, que é OUTRO ponto de entrada — e é o que o passo 1 do roteiro
  # executa num clone limpo. Eles falhavam de formas diferentes: a mensagem
  # estava certa e saía DEPOIS de vinte linhas de rastro de pilha, porque o
  # comando deixava a exceção propagar. Medido na execução do P3.
  # Falha de novo no dia em que alguém tirar o `except` do CLI.
  @api
  Cenário: A restauração sem o banco no ar falha com mensagem clara e sem rastro
    Dado nenhum Postgres acessível na URL configurada
    Quando o comando de restauração é executado
    Então o comando sai com código de erro
    E a saída diz qual comando sobe o banco
    E a saída não contém rastro de pilha
