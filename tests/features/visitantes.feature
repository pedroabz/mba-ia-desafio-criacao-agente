# language: pt
# Origem: docs/spike-dominio-invariantes.md (Fase 1.1)
# ADR: 0005 (autorização de entrada duplicada é recusada)
#
# @pendente = ainda não implementado, FALHA de propósito. Nunca apagar.

Funcionalidade: Autorização de entrada de visitantes

  Contexto:
    Dado o condomínio com os dados iniciais carregados

  # ADR-0005
  @storage
  Cenário: Autorizar a mesma pessoa duas vezes na mesma data é recusado
    Dado que o 101 já autorizou a entrada de Joana Ribeiro em 2030-04-21
    Quando o morador autoriza Joana Ribeiro em 2030-04-21 outra vez
    Então nenhuma autorização nova é criada
    E a resposta informa que a pessoa já está autorizada nessa data

  # REGRESSÃO · ADR-0005 · falha se o índice UNIQUE(apartamento, nome, data)
  # sumir e a duplicata passar a ser gravada em silêncio.
  @storage
  Cenário: Após a recusa, o apartamento continua com exatamente uma autorização
    Dado que o 101 já autorizou a entrada de Joana Ribeiro em 2030-04-21
    Quando o morador tenta autorizar Joana Ribeiro em 2030-04-21 de novo
    Então o 101 tem exatamente uma autorização para Joana Ribeiro em 2030-04-21
