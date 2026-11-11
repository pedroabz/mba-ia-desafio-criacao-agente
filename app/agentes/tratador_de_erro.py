"""A rede que impede qualquer exceção de ferramenta de virar `500`.

ADR-0011, a metade que faltava. Cada agente registra este tratador em
`on_tool_error_callback`, e ele converte **qualquer** exceção de ferramenta em
resposta estruturada para o modelo.

**Por que existe, se cada ferramenta já tem `except RecusaDeNegocio`.** Os dois
mecanismos têm papéis diferentes e não se sobrepõem:

- o `except` **local** existe onde a recusa carrega dado aproveitável — a lista
  de áreas válidas, a identificação da própria reserva. Ele cobre toda recusa
  **prevista**;
- este tratador cobre o **imprevisto**. Uma exceção de um caminho que ninguém
  pensou — um `AttributeError`, um erro de driver — escaparia do `except` local
  e, verificado por execução no spike 1.3, **propaga para fora de
  `runner.run_async`**, derruba o turno e a API responde `500`.

A Garantia 5 proíbe exatamente isso: *"uma reserva vence e a outra é recusada
com uma resposta normal, sem erro de servidor"*. E o passo 14 do avaliador
dispara duas aprovações simultâneas conferindo que **as duas** respondem `200`.

⚠️ **Risco aceito, registrado no ADR-0011:** este tratador captura qualquer
exceção, inclusive bug genuíno. Um `AttributeError` viraria uma recusa
apresentada ao modelo em vez de um erro visível — erro de programação passando
por regra de negócio. A mitigação é o `logger.exception` abaixo: ele **precisa**
registrar o que capturou, senão bug se esconde atrás de recusa.
"""

from __future__ import annotations

import logging
from typing import Any

from google.adk.tools.base_tool import BaseTool

from app.dominio.erros import RecusaDeNegocio

logger = logging.getLogger(__name__)


def tratar_erro_de_ferramenta(
    tool: BaseTool,
    args: dict[str, Any],
    context: Any,
    error: Exception,
) -> dict[str, Any]:
    """Converte a exceção numa resposta que o modelo consegue ler.

    A assinatura é a que o ADK exige (`OnToolErrorCallback`): ferramenta,
    argumentos, contexto e a exceção. Devolver um `dict` substitui o erro por
    essa resposta; devolver `None` deixaria a exceção seguir, que é justamente
    o que não queremos.
    """
    if isinstance(error, RecusaDeNegocio):
        # Recusa prevista que escapou do `except` local da ferramenta. Não é
        # bug: é regra de negócio, e o `warning` basta.
        logger.warning(
            "recusa de negócio escapou da ferramenta %s: %s", tool.name, error
        )
        return {"erro": str(error), "recusado": True}

    # Qualquer outra coisa é bug até prova em contrário, e tem que aparecer no
    # log com rastro de pilha. Sem isto, a decisão do ADR-0011 esconderia
    # defeito atrás de recusa — é o risco que ele aceitou de olhos abertos.
    logger.exception(
        "erro INESPERADO na ferramenta %s com argumentos %r", tool.name, args
    )
    return {
        "erro": (
            "Não consegui completar essa operação agora. Diga ao morador que "
            "houve uma falha e que ele pode tentar de novo; não invente o "
            "resultado da ação."
        ),
        "recusado": True,
    }
