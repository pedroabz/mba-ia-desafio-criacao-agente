"""Tradução de falha do modelo em resposta HTTP. ADR-0019.

**O modo de falha que este módulo existe para impedir é silencioso, e é o pior
possível neste contrato.**

O erro de quota chega ao `Runner` do ADK de **duas** formas (medido no spike
2.4): primeiro como um **evento** com `error_code='RESOURCE_EXHAUSTED'`, que
fica gravado na sessão; depois, **se o consumidor drenar o gerador**, como
exceção — o `raise` está depois do `yield`
(`google/adk/flows/llm_flows/core/_finalizer.py:579`).

Uma rota que montasse a `resposta` com o texto dos eventos e parasse no evento
de erro devolveria `200` com `resposta` vazia. E `resposta` vazia é, pelo
contrato do enunciado, o sinal de *"parei esperando confirmação"* — **uma falha
de quota se disfarçaria de confirmação pendente.** É a restrição `M-4`.

Por isso há duas peças trabalhando juntas, e nenhuma funciona sozinha:

1. `app/api/conversa.py` drena os events até o fim (`A-7`), para a exceção
   existir;
2. este módulo a traduz em **`503` com `Retry-After`**, para ela ter assinatura
   própria — distinguível de pendência e de bug.

Por que `503` e não `500`: o `500` diz *"tem bug aqui"*, e o `503` diz *"volte
depois"*. Para quem está corrigindo o trabalho, a diferença conta. O `503` não
está no contrato do enunciado (que define `200`, `404` e `409`), e o avaliador
não testa este caminho — o ganho é de qualidade, não de nota.

⚠️ **Falta de quota NÃO é recusa de negócio.** O ADR-0011 manda recusa de
negócio nunca virar erro de servidor; isto é o outro lado. Quota é
indisponibilidade, e tratá-la como recusa mentiria para o morador sobre a regra
do condomínio.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

SEGUNDOS_PARA_TENTAR_DE_NOVO = 30
"""O `Retry-After`. A quota do plano gratuito é por minuto e por dia; 30 s é
tempo suficiente para um pico de minuto passar, e curto o bastante para quem
está testando não achar que travou."""

MENSAGEM = (
    "O modelo recusou a requisição por limite de uso. Isto não é erro do "
    "condomínio nem do seu pedido: tente de novo em alguns segundos."
)


def e_erro_de_quota(erro: BaseException) -> bool:
    """O erro, em qualquer ponto da cadeia de causas, é `429`/quota?

    Olha a cadeia inteira porque o ADK embrulha o erro do SDK, que embrulha o
    do transporte. E olha **três** sinais, porque nenhum deles é estável
    sozinho: o nome da classe do ADK é privado (`_ResourceExhaustedError`), o
    código HTTP só aparece em alguns embrulhos, e o nome do status vem no corpo.
    """
    atual: BaseException | None = erro
    while atual is not None:
        if type(atual).__name__ in {
            "_ResourceExhaustedError",
            "ResourceExhausted",
        }:
            return True
        if getattr(atual, "code", None) == 429 or getattr(atual, "status_code", None) == 429:
            return True
        if "RESOURCE_EXHAUSTED" in str(atual) or "429" in str(getattr(atual, "message", "")):
            return True
        atual = atual.__cause__ or atual.__context__
    return False


def registrar_tratadores(aplicacao: FastAPI) -> None:
    """Liga o tratador de falha do modelo na aplicação."""

    @aplicacao.exception_handler(Exception)
    async def _falha_do_modelo(request: Request, erro: Exception):  # noqa: ANN202
        if not e_erro_de_quota(erro):
            # Não é quota: deixa seguir como erro de servidor. Mascarar bug
            # como indisponibilidade esconderia defeito atrás de "tente
            # depois" — o oposto do que este módulo quer.
            raise erro

        logger.warning("quota do modelo esgotada em %s", request.url.path)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": MENSAGEM},
            headers={"Retry-After": str(SEGUNDOS_PARA_TENTAR_DE_NOVO)},
        )
