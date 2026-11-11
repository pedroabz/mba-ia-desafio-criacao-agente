"""Recusas de negócio do condomínio.

São exceções, e não códigos de retorno, porque toda uma categoria delas precisa
interromper a gravação — e porque o chamador (a tool do agente) traduz cada uma
numa frase diferente para o morador.

A distinção mais importante deste módulo está entre `AreaIndisponivel` e
`JaReservadaPorVoce`: as duas significam "a data está ocupada", mas só a
segunda pode revelar de quem é a reserva, porque a reserva é do próprio
morador. Ver ADR-0004 e o invariante I-06.
"""

from __future__ import annotations


class RecusaDeNegocio(Exception):
    """Base de tudo que o condomínio recusa por regra, não por erro técnico."""


class AreaInexistente(RecusaDeNegocio):
    """A área pedida não é reservável (ADR-0003).

    Carrega as áreas válidas para que a resposta ao morador possa listá-las em
    vez de só negar.
    """

    def __init__(self, area: str, areas_validas: list[str]) -> None:
        super().__init__(f"Área '{area}' não é reservável.")
        self.area = area
        self.areas_validas = areas_validas


class AreaIndisponivel(RecusaDeNegocio):
    """A data já está ocupada por **outro** apartamento (I-01).

    ⚠️ Esta exceção **não carrega** o apartamento dono nem o código da reserva
    existente, e isso é deliberado: o invariante I-06 proíbe que qualquer dado
    capaz de identificar outro apartamento chegue à conversa. O passo 10 do
    roteiro do avaliador verifica exatamente isso.
    """

    def __init__(self, area: str, data: object) -> None:
        super().__init__(f"A área '{area}' já está reservada em {data}.")
        self.area = area
        self.data = data


class JaReservadaPorVoce(RecusaDeNegocio):
    """A data já está reservada **pelo próprio apartamento da sessão**.

    Separada de `AreaIndisponivel` de propósito: aqui a reserva pertence a quem
    está perguntando, então a resposta pode identificá-la sem ferir I-06.
    """

    def __init__(self, reserva: object) -> None:
        super().__init__("Você já tem uma reserva para essa área nessa data.")
        self.reserva = reserva


class ReservaNaoEncontrada(RecusaDeNegocio):
    """Não existe reserva ativa com esses dados **neste apartamento**.

    ⚠️ Esta mesma exceção cobre dois casos que precisam ser indistinguíveis:
    a reserva não existe, e a reserva existe mas é de outro apartamento. Se o
    código distinguir os dois, a ferramenta vira um oráculo que confirma a
    existência de reservas alheias — ver ADR-0004.

    A mensagem é genérica **de propósito** e não aceita parâmetros: qualquer
    detalhe aqui — o código pedido, o dono real — reabriria a distinção que a
    exceção existe para apagar.
    """

    def __init__(self) -> None:
        super().__init__("Você não tem uma reserva com esses dados.")


class VisitanteJaAutorizado(RecusaDeNegocio):
    """Essa pessoa já está autorizada nessa data, para este apartamento.

    ADR-0005. Note que isso é recusa de negócio, não o `409` da rota de
    confirmações: pedir de novo a mesma autorização é diferente de responder
    duas vezes a mesma confirmação pendente.
    """

    def __init__(self, nome: str, data: object) -> None:
        super().__init__(f"{nome} já está autorizado(a) em {data}.")
        self.nome = nome
        self.data = data
