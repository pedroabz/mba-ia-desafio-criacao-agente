"""Apoio compartilhado pelas ferramentas: apartamento, data e recusas."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.dominio.erros import RecusaDeNegocio


class DataInvalida(RecusaDeNegocio):
    """A data não veio no formato AAAA-MM-DD.

    É recusa de negócio, não erro: o modelo lê a mensagem e pode tentar de
    novo com o formato certo (ADR-0010).
    """

    def __init__(self, valor: str) -> None:
        super().__init__(
            f"'{valor}' não é uma data válida. Use o formato AAAA-MM-DD, "
            "como 2030-04-20."
        )
        self.valor = valor


def apartamento_da_sessao(tool_context: Any) -> str:
    """Lê o apartamento do state da sessão.

    **É o único lugar de onde o apartamento pode vir.** Ele foi posto ali na
    criação da sessão e representa o morador autenticado; nenhuma ferramenta
    o aceita como parâmetro, e por isso nada que o morador escreva o altera
    (`I-02`, Garantia 2).
    """
    apartamento = tool_context.state.get("apartamento")
    if not apartamento:
        # Não é recusa de negócio: é sessão malformada, e falhar alto aqui é
        # melhor que operar sobre apartamento nenhum.
        raise RuntimeError("A sessão não tem apartamento no state.")
    return str(apartamento)


def converter_data(valor: str) -> date:
    """Converte AAAA-MM-DD, recusando qualquer outra coisa (ADR-0010)."""
    try:
        return date.fromisoformat(valor)
    except (ValueError, TypeError):
        raise DataInvalida(valor) from None


def recusa(excecao: RecusaDeNegocio, **extras: Any) -> dict[str, Any]:
    """Traduz uma recusa de negócio no dicionário que o modelo lê.

    ADR-0011 — recusa **nunca** escapa como exceção: verificado que uma
    exceção saindo de uma ferramenta propaga para fora de `runner.run_async`
    e a API responde 500, que é o que a Garantia 5 proíbe.

    Os `extras` existem para as recusas que carregam informação útil —
    `AreaInexistente` traz a lista de áreas válidas, `JaReservadaPorVoce` traz
    a reserva do próprio morador. Sem elas a resposta seria só "recusado", e
    o modelo não teria como ajudar.
    """
    return {"erro": str(excecao), **extras}
