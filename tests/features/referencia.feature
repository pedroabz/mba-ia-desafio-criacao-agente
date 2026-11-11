# language: pt
# Origem: docs/spike-dominio-invariantes.md (Fase 1.1)
# ADR: 0002 (apartamentos e áreas semeados no SQLite)
#
# @pendente = ainda não implementado, FALHA de propósito. Nunca apagar.

Funcionalidade: Dados de referência do condomínio

  # ADR-0002
  @storage
  Cenário: Seed carrega os dados de referência a partir de dados/
    Dado um banco vazio
    Quando o seed é executado
    Então existem 6 apartamentos
    E existem 3 áreas
    E a taxa do salão de festas é 150.0
    E a taxa da quadra é 0

  # REGRESSÃO · exigência do passo 15 do avaliador: os arquivos de dados/
  # precisam ficar byte-idênticos aos do repositório base. Falha se qualquer
  # código escrever neles.
  @storage
  Cenário: Os arquivos de dados permanecem intactos após uso
    Dado o condomínio com os dados iniciais carregados
    Quando reservas são criadas e canceladas
    E visitantes são autorizados
    Então os arquivos em dados/ continuam byte-idênticos aos originais

  # ADR-0002 · integridade referencial vinda do banco
  @storage
  Cenário: Reserva não pode apontar para área inexistente
    Dado o condomínio com os dados iniciais carregados
    Quando se tenta gravar uma reserva da área "piscina"
    Então a gravação é recusada pelo banco
