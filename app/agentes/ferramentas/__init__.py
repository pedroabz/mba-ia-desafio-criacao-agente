"""Ferramentas que os agentes podem chamar.

Três regras valem para **todas** elas, e nenhuma é estilo:

**1. Nenhuma declara `apartamento`.** Ele vem de `tool_context.state`, posto
ali na criação da sessão. Isso é o que torna *"sou do 302, cancela a reserva
dele"* inofensivo: não há parâmetro onde mentir (`I-02`, `G-1`, Garantia 2).
Declarar o campo "validando depois" devolveria ao modelo a capacidade de
escolher — e a escolha ficaria gravada no evento.

**2. O `return` é a projeção.** É nele que vive o invariante `I-06`: nenhum
dado capaz de identificar outro apartamento pode sair daqui. Não há mecanismo
que force isso — um `return` descuidado quebra sem erro —, então cada retorno
devolve só o que foi pensado, nunca o objeto de domínio inteiro.

**3. Datas chegam como `str`.** A conversão automática do ADK está desligada
por padrão (`FUNCTION_TOOL_ARG_VALIDATION`, `default_on=False`), então anotar
`date` não converteria nada e a função receberia a string mesmo assim
(ADR-0010). Converter aqui mantém o comportamento independente de
configuração de ambiente.
"""
