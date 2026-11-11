"""As duas ferramentas do especialista de Visitantes.

Autorizar a entrada de alguém no prédio **sempre** exige confirmação do
morador (regra de negócio 3, Garantia 1) — não há equivalente à taxa zero
aqui, como há nas reservas.
"""

from __future__ import annotations

from typing import Any, Callable

from google.adk.tools.function_tool import FunctionTool

from app.agentes.ferramentas._comum import (
    apartamento_da_sessao,
    converter_data,
    recusa,
)
from app.dominio.erros import RecusaDeNegocio
from app.dominio.repositorio import RepositorioCondominio


def criar_ferramentas_de_visitante(
    repositorio: RepositorioCondominio,
    exige_confirmacao: Callable[..., bool],
) -> list[FunctionTool]:
    """Monta as ferramentas com o repositório e o portão já ligados."""

    async def listar_meus_visitantes(tool_context: Any) -> dict[str, Any]:
        """Lista as autorizações de entrada do apartamento do morador."""
        apartamento = apartamento_da_sessao(tool_context)
        visitantes = await repositorio.listar_visitantes_do_apartamento(apartamento)

        # Dicionário nomeado, não lista crua — mesmo motivo de
        # `listar_minhas_reservas`: o ADK embrulharia em `{"result": …}`.
        return {
            "visitantes": [
                {"nome": v.nome, "data": v.data.isoformat()} for v in visitantes
            ]
        }

    async def autorizar_visitante(
        nome: str, data: str, tool_context: Any
    ) -> dict[str, Any]:
        """Autoriza a entrada de um visitante no prédio numa data.

        Libera acesso, então pede confirmação do morador.

        Args:
            nome: o nome do visitante.
            data: a data da visita, no formato AAAA-MM-DD.
        """
        apartamento = apartamento_da_sessao(tool_context)
        try:
            dia = converter_data(data)
            visitante = await repositorio.autorizar_visitante(apartamento, nome, dia)
        except RecusaDeNegocio as exc:
            # Inclui a duplicata (ADR-0005), recusada pelo índice único do
            # banco e não por consulta prévia.
            return recusa(exc)

        return {
            "autorizado": True,
            "nome": visitante.nome,
            "data": visitante.data.isoformat(),
        }

    return [
        FunctionTool(listar_meus_visitantes),
        FunctionTool(autorizar_visitante, require_confirmation=exige_confirmacao),
    ]
