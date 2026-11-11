"""Rotas de sessão e de conversa. As seis do contrato, todas implementadas.

As duas de conversa — mensagens e confirmações — são as mais delicadas do
desafio, e o que as governa não está aqui: está em `app/api/conversa.py`
(as regras `A-3`, `A-5`, `A-7`, `A-9`) e em `app/api/pendencias.py` (a varredura
e a lista branca de `detalhes`). Estas funções são a casca HTTP.

A divisão não é estética. O enunciado chama a confirmação de "a armadilha mais
cara deste desafio" e avisa que a rota pode aceitar a resposta, não dar erro
nenhum e a ação não executar. Cada regra que impede isso está nomeada e
comentada onde mora.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.dependencias import (
    ConversaDoApp,
    Repositorio,
    SessaoExistente,
    Sessoes,
)
from app.api.esquemas import (
    ConfirmacaoPendenteResposta,
    ConversaResposta,
    CriarSessaoRequisicao,
    CriarSessaoResposta,
    EnviarMensagemRequisicao,
    ErroResposta,
    EventoResposta,
    ResponderConfirmacaoRequisicao,
)

roteador = APIRouter(prefix="/sessoes", tags=["conversa"])

SESSAO_NAO_ENCONTRADA = {
    status.HTTP_404_NOT_FOUND: {"model": ErroResposta, "description": "Sessão não encontrada"}
}


@roteador.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=CriarSessaoResposta,
    summary="Cria uma sessão para um apartamento",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErroResposta,
            "description": "Apartamento inexistente em dados/apartamentos.json",
        }
    },
)
async def criar_sessao(
    requisicao: CriarSessaoRequisicao,
    sessoes: Sessoes,
    repositorio: Repositorio,
) -> CriarSessaoResposta:
    """`POST /sessoes` com `{"apartamento": "101"}` -> `201 {"session_id": "..."}`

    GARANTIA 2 — este é o ÚNICO ponto do sistema em que o apartamento de uma
    sessão é definido. Ele vem do corpo desta requisição (que representa o
    morador autenticado), vai para o state da sessão e não existe nenhuma
    operação, em nenhuma rota, que o altere depois. Nada que o morador escreva
    nas mensagens seguintes passa por aqui.

    DECISÃO (o enunciado deixa livre): apartamento que não existe em
    `dados/apartamentos.json` recebe `404` e NENHUMA sessão é criada. Motivo: o
    apartamento é a credencial da sessão — é o que o enunciado chama de "morador
    autenticado" e é a base inteira da Garantia 2. Criar sessão para um
    apartamento inexistente produziria uma conversa sem dono, cujas tools
    operariam sobre um apartamento fantasma; falhar na porta de entrada é mais
    seguro e mais fácil de depurar do que descobrir isso três mensagens depois.
    Escolhi `404` (e não `422`) porque o problema não é o formato do corpo: o
    campo é um `str` válido, o que não existe é o recurso referenciado.
    """
    if not await repositorio.apartamento_existe(requisicao.apartamento):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Apartamento '{requisicao.apartamento}' não existe no condomínio.",
        )

    sessao = await sessoes.criar_sessao(requisicao.apartamento)
    return CriarSessaoResposta(session_id=sessao.id)


@roteador.get(
    "/{session_id}/eventos",
    response_model=list[EventoResposta],
    summary="Todos os eventos da sessão, em ordem",
    responses=SESSAO_NAO_ENCONTRADA,
)
async def listar_eventos(
    sessao: SessaoExistente,
    sessoes: Sessoes,
) -> list[EventoResposta]:
    """`GET /sessoes/{session_id}/eventos` -> `200` com a lista completa.

    Devolve todos os eventos gravados na sessão, em ordem de gravação, com o
    conteúdo completo de cada um (`conteudo` é um dicionário de passagem).
    Sessão inexistente -> `404`, aplicado pela dependência `SessaoExistente`
    (passo 9 do fluxo do avaliador).
    """
    eventos = await sessoes.listar_eventos(sessao.id)
    return [
        EventoResposta(
            id=evento.id,
            autor=evento.autor,
            timestamp=evento.timestamp,
            conteudo=evento.conteudo,
        )
        for evento in eventos
    ]


# ---------------------------------------------------------------------------
# AS DUAS ROTAS DE CONVERSA
#
# O `404` de sessão inexistente vem da dependência `SessaoExistente`, e vem
# ANTES de qualquer execução — inclusive antes de acionar o ADK.
# ---------------------------------------------------------------------------


@roteador.post(
    "/{session_id}/mensagens",
    response_model=ConversaResposta,
    summary="Envia uma mensagem do morador para o assistente",
    responses=SESSAO_NAO_ENCONTRADA,
)
async def enviar_mensagem(
    sessao: SessaoExistente,
    requisicao: EnviarMensagemRequisicao,
    conversa: ConversaDoApp,
) -> ConversaResposta:
    """`POST /sessoes/{session_id}/mensagens` com `{"texto": "..."}`.

    `200` com `{"resposta": str, "confirmacoes_pendentes": [...]}`.

    ⚠️ **`resposta` vem VAZIA quando o fluxo parou esperando confirmação**, e
    isso é informação, não falta dela (`A-5`). Nada neste arquivo escreve uma
    frase nesse campo: ele carrega só o que o **agente principal** disse
    (`A-9`).

    ⚠️ **Esta rota nunca aprova nada** (`A-4`). Se o morador escrever "sim,
    confirmo", isto é um pedido novo — texto não retoma ação pendente, e o
    passo 11 do avaliador testa exatamente isso. Aprovar é a outra rota.

    O apartamento vem de `sessao`, que saiu da nossa tabela a partir do
    `session_id` da URL. **Nunca do texto da mensagem** (Garantia 2).
    """
    resultado = await conversa.enviar_texto(sessao, requisicao.texto)
    return ConversaResposta(
        resposta=resultado.resposta,
        confirmacoes_pendentes=[
            ConfirmacaoPendenteResposta(
                id=pendente.id, acao=pendente.acao, detalhes=pendente.detalhes
            )
            for pendente in resultado.confirmacoes_pendentes
        ],
    )


@roteador.post(
    "/{session_id}/confirmacoes",
    response_model=ConversaResposta,
    summary="Responde uma confirmação pendente (aprova ou nega)",
    responses={
        **SESSAO_NAO_ENCONTRADA,
        status.HTTP_409_CONFLICT: {
            "model": ErroResposta,
            "description": "Não existe confirmação pendente com esse id nesta sessão",
        },
    },
)
async def responder_confirmacao(
    sessao: SessaoExistente,
    requisicao: ResponderConfirmacaoRequisicao,
    conversa: ConversaDoApp,
) -> ConversaResposta:
    """`POST /sessoes/{session_id}/confirmacoes` com `{"id": ..., "confirmado": ...}`.

    `200` no mesmo formato da rota de mensagens, ou **`409`** quando não existe
    confirmação pendente com aquele `id` nesta sessão.

    ⚠️ **O `409` cobre três casos com uma pergunta só** (`A-2`): `id` que não
    existe, `id` de outra sessão e `id` **já respondido**. Nos três, ele
    simplesmente não está na lista de pendências desta conversa. E nos três
    **nada executa** — é o passo 8 do roteiro, que reenvia o mesmo `id` e
    confere que continua existindo exatamente uma reserva.

    ⚠️ **A checagem vem antes de acionar o ADK** (`A-1`). Depois é tarde:
    medido, um `id` que o ADK não reconhece faz ele quebrar com `ValueError` e
    a rota responder `500`.
    """
    from app.api.conversa import ConfirmacaoNaoPendente

    try:
        resultado = await conversa.responder_confirmacao(
            sessao, requisicao.id, requisicao.confirmado
        )
    except ConfirmacaoNaoPendente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Não existe confirmação pendente com o id '{requisicao.id}' "
                "nesta sessão."
            ),
        ) from None

    return ConversaResposta(
        resposta=resultado.resposta,
        confirmacoes_pendentes=[
            ConfirmacaoPendenteResposta(
                id=pendente.id, acao=pendente.acao, detalhes=pendente.detalhes
            )
            for pendente in resultado.confirmacoes_pendentes
        ],
    )
