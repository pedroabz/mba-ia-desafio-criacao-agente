# language: pt
# Origem: docs/spike-dominio-invariantes.md (Fase 1.1)
# Invariante: I-02 (operação age só sobre o apartamento da sessão)
#
# @pendente = ainda não implementado, FALHA de propósito. Nunca apagar.

Funcionalidade: A sessão pertence a um apartamento

  # REGRESSÃO · I-02 · Garantia 2 · passo 3 do avaliador.
  # O alicerce já existe em app/dominio/sessao.py: Sessao é frozen e a
  # interface não tem operação de update. Este cenário falha se alguém
  # acrescentar um caminho que troque o apartamento de uma sessão.
  @conversa
  Cenário: A sessão não troca de dono
    Dado uma sessão do 101
    Quando o morador afirma ser do 302
    Então as tools continuam operando sobre o 101
    E nem a resposta nem os eventos trazem dados do 302
