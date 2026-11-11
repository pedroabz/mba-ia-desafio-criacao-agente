"""Injeção de dependências das rotas.

As rotas recebem as duas seams (`RepositorioCondominio` e `ServicoSessao`) por
aqui, sempre pelo tipo da interface. Quem decide a implementação concreta é
`criar_app()`, em `app/api/aplicacao.py` — é isso que permite que as tasks 1.3
e a Fase 2 troquem a implementação sem tocar em nenhuma rota.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Path, Request, status

from app.dominio.repositorio import RepositorioCondominio
from app.dominio.sessao import Sessao, ServicoSessao


# `async def` de propósito: dependência síncrona no FastAPI é despachada para
# um threadpool, o que não faz sentido para uma leitura de atributo.
async def obter_repositorio(request: Request) -> RepositorioCondominio:
    return request.app.state.repositorio


async def obter_servico_sessao(request: Request) -> ServicoSessao:
    return request.app.state.servico_sessao


async def obter_conversa(request: Request):
    """O orquestrador de turn, ou `503` se a aplicação subiu sem ele.

    `criar_app` só monta a conversa quando o serviço de sessão é o do ADK — um
    serviço falso injetado por teste deixa as rotas de conversa indisponíveis.
    Responder `503` aqui é melhor que estourar `AttributeError` em `None`: diz
    que a capacidade não existe nesta montagem, em vez de parecer bug.
    """
    conversa = getattr(request.app.state, "conversa", None)
    if conversa is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Esta instância subiu sem o runtime de conversa do ADK.",
        )
    return conversa


Repositorio = Annotated[RepositorioCondominio, Depends(obter_repositorio)]
Sessoes = Annotated[ServicoSessao, Depends(obter_servico_sessao)]
ConversaDoApp = Annotated[object, Depends(obter_conversa)]


async def obter_sessao_existente(
    session_id: Annotated[str, Path(description="`session_id` devolvido por POST /sessoes")],
    sessoes: Sessoes,
) -> Sessao:
    """Resolve o `{session_id}` do caminho, ou responde `404`.

    CONTRATO: "As rotas com `{session_id}` no caminho respondem `404` quando a
    sessão não existe." Esta dependência é o único lugar que implementa essa
    regra, e toda rota com `{session_id}` a declara — inclusive as rotas de
    mensagens e confirmações (task 3.2), onde o `404` precisa vir ANTES de
    qualquer tentativa de executar o agente.

    Conferido no passo 9 do fluxo do avaliador
    (`GET /sessoes/sessao-inexistente/eventos` -> `404`).
    """
    sessao = await sessoes.buscar_sessao(session_id)
    if sessao is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sessão '{session_id}' não encontrada.",
        )
    return sessao


SessaoExistente = Annotated[Sessao, Depends(obter_sessao_existente)]
