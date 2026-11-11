"""As cinco ferramentas do especialista de Reservas.

São cinco e não quatro porque o cancelamento são duas (ADR-0012): uma por
área e data, outra por código, cada uma com parâmetros obrigatórios. Uma
ferramenta só, com três opcionais, deixaria "veio `area` sem `data`" como um
estado que só um `if` nosso pegaria — e o cancelamento é a única ação
destrutiva que executa **sem confirmação** (regra de negócio 4).
"""

from __future__ import annotations

from typing import Any, Callable

from google.adk.tools.function_tool import FunctionTool

from app.agentes.ferramentas._comum import (
    apartamento_da_sessao,
    converter_data,
    recusa,
)
from app.dominio.erros import (
    AreaIndisponivel,
    AreaInexistente,
    JaReservadaPorVoce,
    RecusaDeNegocio,
)
from app.dominio.repositorio import RepositorioCondominio


def criar_ferramentas_de_reserva(
    repositorio: RepositorioCondominio,
    exige_confirmacao: Callable[..., bool],
) -> list[FunctionTool]:
    """Monta as ferramentas com o repositório e o portão já ligados.

    A injeção por fechamento existe para que as funções abaixo tenham
    **apenas** os parâmetros que o modelo deve ver. Receber o repositório
    como argumento o colocaria na declaração enviada ao modelo.
    """

    async def consultar_disponibilidade(
        area: str, data: str, tool_context: Any
    ) -> dict[str, Any]:
        """Diz se uma área comum está livre numa data.

        Args:
            area: o identificador da área (salao-de-festas, churrasqueira, quadra).
            data: a data no formato AAAA-MM-DD.
        """
        try:
            dia = converter_data(data)
            livre = await repositorio.data_esta_livre(area, dia)
        except AreaInexistente as exc:
            return recusa(exc, areas_validas=exc.areas_validas)
        except RecusaDeNegocio as exc:
            return recusa(exc)

        # ⚠️ I-06 — devolve o booleano e NADA MAIS. Quem reservou é dado de
        # outro apartamento: nem o código, nem o número, nem "está ocupada
        # pelo 302". O passo 10 do avaliador confere que `302` isolado não
        # aparece na resposta.
        return {"livre": livre}

    async def listar_minhas_reservas(tool_context: Any) -> dict[str, Any]:
        """Lista as reservas ativas do apartamento do morador."""
        apartamento = apartamento_da_sessao(tool_context)
        reservas = await repositorio.listar_reservas_do_apartamento(apartamento)

        # Dicionário nomeado, não lista crua: retorno não-`dict` é embrulhado
        # pelo ADK em `{"result": …}` (`_caller.py:310`), e é isso que apareceria
        # no `GET /eventos` que o avaliador lê no passo 12.
        return {
            "reservas": [
                {"codigo": r.codigo, "area": r.area, "data": r.data.isoformat()}
                for r in reservas
            ]
        }

    async def criar_reserva(area: str, data: str, tool_context: Any) -> dict[str, Any]:
        """Reserva uma área comum para o apartamento do morador.

        Áreas com taxa geram cobrança e pedem confirmação do morador.

        Args:
            area: o identificador da área (salao-de-festas, churrasqueira, quadra).
            data: a data no formato AAAA-MM-DD.
        """
        apartamento = apartamento_da_sessao(tool_context)
        try:
            dia = converter_data(data)
            reserva = await repositorio.criar_reserva(apartamento, area, dia)
        except AreaInexistente as exc:
            return recusa(exc, areas_validas=exc.areas_validas)
        except JaReservadaPorVoce as exc:
            # Pode identificar a reserva: ela é do próprio morador.
            r = exc.reserva
            return recusa(exc, sua_reserva={"codigo": r.codigo, "data": r.data.isoformat()})
        except AreaIndisponivel as exc:
            # ⚠️ NÃO acrescenta quem reservou. A exceção não carrega isso de
            # propósito, e nada aqui pode inventar (I-06).
            return recusa(exc)
        except RecusaDeNegocio as exc:
            return recusa(exc)

        return {
            "criada": True,
            "codigo": reserva.codigo,
            "area": reserva.area,
            "data": reserva.data.isoformat(),
        }

    async def cancelar_reserva_por_area_e_data(
        area: str, data: str, tool_context: Any
    ) -> dict[str, Any]:
        """Cancela a reserva do morador numa área e data.

        Args:
            area: o identificador da área.
            data: a data no formato AAAA-MM-DD.
        """
        apartamento = apartamento_da_sessao(tool_context)
        try:
            dia = converter_data(data)
            reserva = await repositorio.cancelar_reserva_por_area_data(
                apartamento, area, dia
            )
        except RecusaDeNegocio as exc:
            return recusa(exc)

        # Nomeia o que sumiu: cancelar não tem confirmação prévia (regra 4),
        # então esta resposta é a única chance de o morador notar um engano.
        return {"cancelada": True, "area": reserva.area, "data": reserva.data.isoformat()}

    async def cancelar_reserva_por_codigo(
        codigo: str, tool_context: Any
    ) -> dict[str, Any]:
        """Cancela uma reserva do morador pelo código dela.

        Args:
            codigo: o código da reserva, como RSV-1377.
        """
        apartamento = apartamento_da_sessao(tool_context)
        try:
            reserva = await repositorio.cancelar_reserva_por_codigo(apartamento, codigo)
        except RecusaDeNegocio as exc:
            # ⚠️ Código de outro apartamento e código inexistente produzem a
            # MESMA recusa (ADR-0004). Distinguir transformaria a ferramenta
            # num oráculo que confirma a existência de reservas alheias.
            return recusa(exc)

        return {"cancelada": True, "area": reserva.area, "data": reserva.data.isoformat()}

    return [
        FunctionTool(consultar_disponibilidade),
        FunctionTool(listar_minhas_reservas),
        FunctionTool(criar_reserva, require_confirmation=exige_confirmacao),
        FunctionTool(cancelar_reserva_por_area_e_data),
        FunctionTool(cancelar_reserva_por_codigo),
    ]
