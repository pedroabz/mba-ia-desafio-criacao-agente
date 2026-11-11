"""Rotas de verificação: leem os dados do condomínio DIRETO, sem o modelo.

São as rotas que o avaliador usa para conferir os efeitos de cada conversa.
Em produção ficariam atrás de acesso administrativo; aqui existem para a
correção. Nenhum agente, nenhuma chamada ao Gemini: caminho repositório ->
HTTP e nada mais.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path

from app.api.dependencias import Repositorio
from app.api.esquemas import ReservaResposta, VisitanteResposta

roteador = APIRouter(prefix="/apartamentos", tags=["verificação"])

NumeroDoApartamento = Annotated[
    str, Path(description="Número do apartamento, como em dados/apartamentos.json")
]


@roteador.get(
    "/{numero}/reservas",
    response_model=list[ReservaResposta],
    summary="Reservas ativas de um apartamento",
)
async def listar_reservas(numero: NumeroDoApartamento, repositorio: Repositorio):
    """`GET /apartamentos/101/reservas` ->
    `[{"codigo": "RSV-1377", "area": "quadra", "data": "2030-03-09"}]`

    DECISÃO (o enunciado deixa livre): apartamento que não existe em
    `dados/apartamentos.json` recebe `200` com lista vazia, não `404`. Motivo:
    esta é uma rota de *verificação de estado* — a pergunta que ela responde é
    "quais reservas existem para este número?", e a resposta honesta para um
    número sem reservas é a lista vazia. Devolver `404` obrigaria o avaliador a
    distinguir dois significados de erro numa rota cujo papel é só reportar
    fatos. Note que a escolha é diferente na criação de sessão (ver
    `rotas_sessoes.criar_sessao`), e de propósito: lá o apartamento é
    credencial, aqui é só um filtro de consulta.
    """
    reservas = await repositorio.listar_reservas_do_apartamento(numero)
    # O campo `apartamento` do domínio é deliberadamente descartado: não faz
    # parte do contrato da resposta.
    return [
        ReservaResposta(codigo=reserva.codigo, area=reserva.area, data=reserva.data)
        for reserva in reservas
    ]


@roteador.get(
    "/{numero}/visitantes",
    response_model=list[VisitanteResposta],
    summary="Autorizações de visita de um apartamento",
)
async def listar_visitantes(numero: NumeroDoApartamento, repositorio: Repositorio):
    """`GET /apartamentos/302/visitantes` ->
    `[{"nome": "Marina Duarte", "data": "2030-03-16"}]`

    Mesma decisão da rota de reservas para apartamento inexistente: `200` com
    lista vazia.
    """
    visitantes = await repositorio.listar_visitantes_do_apartamento(numero)
    return [
        VisitanteResposta(nome=visitante.nome, data=visitante.data) for visitante in visitantes
    ]
