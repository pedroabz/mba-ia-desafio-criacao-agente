"""Liga os arquivos .feature ao pytest.

Cada cenário vira um teste. Enquanto um passo não tiver implementação, o
teste FALHA com `StepDefinitionNotFoundError`, dizendo exatamente qual passo
falta — que é o estado desejado para cenário pendente.

Nao use @skip nem xfail aqui: teste pulado e invisivel, e invisivel e o mesmo
que perdido. A suite precisa doer enquanto houver cenario por implementar.

As implementacoes dos passos entram em tests/steps/, por tema.
"""

from __future__ import annotations

from pytest_bdd import scenarios

# O diretório inteiro, não um arquivo por linha. Registrar à mão parece mais
# explícito e tem um modo de falha silencioso: arquivo .feature novo fica
# invisível até alguém lembrar de registrá-lo, e cenário não coletado não
# existe. Já aconteceu aqui — persistencia.feature passou despercebido.
scenarios("features")
