"""Interface (seam) de acesso aos dados do condomínio.

Este módulo define **só o contrato**. As rotas da API e, mais adiante, as tools
dos agentes dependem desta interface e nunca de uma implementação concreta.

Por que a seam existe
---------------------
A escolha do armazenamento definitivo é das tasks 1.2/1.3 do `TODO.md`
(Postgres, por causa da Garantia 5: a exclusividade de uma reserva
por área/data precisa valer no instante da gravação, o que pede um índice único
do banco, não um `SELECT` antes do `INSERT`). Programando contra esta interface,
a 1.3 troca **apenas a implementação** — nenhuma rota é tocada.

Métodos são `async` de propósito: o armazenamento definitivo será assíncrono
(asyncpg / SQLAlchemy asyncio) e o enunciado cita "padrão async" como
conceito do curso. Uma implementação síncrona (como a em memória) só precisa
declarar os métodos como `async def` e retornar direto.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from app.dominio.modelos import Area, Reserva, Visitante


@runtime_checkable
class RepositorioCondominio(Protocol):
    """Acesso de leitura/escrita aos dados do condomínio.

    Nesta task (3.1) só as leituras usadas pelas rotas de verificação estão
    declaradas. As escritas (reservar, cancelar, autorizar visitante) entram
    junto com as tools dos agentes, na Fase 2, e serão acrescentadas aqui.
    """

    async def listar_reservas_do_apartamento(self, apartamento: str) -> list[Reserva]:
        """Reservas ativas de um apartamento, em ordem estável.

        Usado por `GET /apartamentos/{numero}/reservas`, que lê os dados
        direto, sem passar pelo modelo. Apartamento sem reservas (ou que não
        existe) devolve lista vazia — nunca erro.
        """
        ...

    async def listar_visitantes_do_apartamento(self, apartamento: str) -> list[Visitante]:
        """Autorizações de visita de um apartamento, em ordem estável.

        Usado por `GET /apartamentos/{numero}/visitantes`. Mesma semântica de
        lista vazia do método acima.
        """
        ...

    async def apartamento_existe(self, numero: str) -> bool:
        """Diz se o número consta nos apartamentos do condomínio.

        Usado na criação da sessão: o apartamento representa o morador
        autenticado (Garantia 2), então vale conferir que ele existe de fato.
        """
        ...

    # -- leituras de referência -------------------------------------------

    async def listar_areas(self) -> list[Area]:
        """Todas as áreas reserváveis, com suas taxas.

        A taxa é o que decide se reservar exige confirmação (regra de negócio 2
        e Garantia 1), então esta leitura é o que sustenta essa decisão —
        nenhuma tabela de taxas vive no prompt do agente.
        """
        ...

    async def buscar_area(self, area_id: str) -> Area | None:
        """Devolve a área, ou `None` se o id não existir (ADR-0003)."""
        ...

    # -- disponibilidade ---------------------------------------------------

    async def data_esta_livre(self, area: str, data: date) -> bool:
        """Diz **apenas** se a data está livre para a área.

        ⚠️ O retorno é um booleano de propósito, e nunca deve virar "quem
        reservou". Checar disponibilidade exige olhar a agenda da área, o que o
        enunciado permite explicitamente — o que não pode é o dono chegar à
        conversa (invariante I-06, passo 10 do avaliador).
        """
        ...

    # -- escritas ----------------------------------------------------------

    async def criar_reserva(self, apartamento: str, area: str, data: date) -> Reserva:
        """Cria uma reserva para o apartamento da sessão e devolve o registro.

        O `codigo` é gerado aqui, nunca recebido de fora — regra de negócio 5.

        A exclusividade vale **no instante da gravação**, imposta por índice
        único do banco e não por consulta prévia (Garantia 5): entre consultar e
        gravar, outro morador pode entrar.

        Raises:
            AreaInexistente: a área não é reservável.
            JaReservadaPorVoce: o próprio apartamento já reservou essa data.
            AreaIndisponivel: outro apartamento já reservou essa data.
        """
        ...

    async def cancelar_reserva_por_area_data(
        self, apartamento: str, area: str, data: date
    ) -> Reserva:
        """Cancela a reserva ativa do apartamento naquela área e data.

        Devolve a reserva cancelada, para que a resposta ao morador possa
        nomear o que sumiu — o cancelamento não tem confirmação prévia, então a
        resposta é a única chance de ele perceber um engano (ADR-0004).

        Raises:
            ReservaNaoEncontrada: não há reserva ativa com esses dados **neste**
                apartamento. Mesma exceção se a reserva pertencer a outro.
        """
        ...

    async def cancelar_reserva_por_codigo(self, apartamento: str, codigo: str) -> Reserva:
        """Cancela pelo código, **validando o dono** (ADR-0004).

        Raises:
            ReservaNaoEncontrada: o código não existe **ou** não é deste
                apartamento. Os dois casos produzem a mesma exceção de
                propósito: distinguir confirmaria a existência de reserva
                alheia (I-06).
        """
        ...

    async def autorizar_visitante(self, apartamento: str, nome: str, data: date) -> Visitante:
        """Registra a autorização de entrada.

        Raises:
            VisitanteJaAutorizado: já existe autorização para essa tripla
                `(apartamento, nome, data)` — ADR-0005.
        """
        ...
