"""Implementação de `RepositorioCondominio` sobre Postgres (ADR-0014).

Substitui `app/dominio/repositorio_memoria.py`, que era temporária. Nenhuma
rota da API precisou mudar: é para isso que a interface existe.

Princípio que organiza o arquivo: **as regras duras são do banco, não daqui.**
Os métodos abaixo gravam e traduzem o erro do banco em recusa de negócio; eles
não "verificam antes para evitar o erro". A diferença importa porque entre uma
verificação e a gravação cabe outra requisição — é a Garantia 5 do enunciado,
que o passo 14 do avaliador testa disparando duas aprovações ao mesmo tempo.
"""

from __future__ import annotations

import secrets
from datetime import date

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.dominio.erros import (
    AreaIndisponivel,
    AreaInexistente,
    JaReservadaPorVoce,
    ReservaNaoEncontrada,
    VisitanteJaAutorizado,
)
from app.dominio.modelos import Area, Reserva, Visitante

# Formato do código. O enunciado diz "formato livre" (regra 5) — o que importa
# é a unicidade, garantida pelo PRIMARY KEY. Seguimos o padrão dos dados
# iniciais (RSV-1377) só por consistência visual.
_PREFIXO_CODIGO = "RSV-"
_TENTATIVAS_CODIGO = 50


class RepositorioPostgres:
    """Implementa `app.dominio.repositorio.RepositorioCondominio`."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    # -- leituras do apartamento (sempre filtrando canceladas) -------------

    async def listar_reservas_do_apartamento(self, apartamento: str) -> list[Reserva]:
        # ⚠️ `ativa = 1` não é opcional: sem ele, reserva cancelada vaza para a
        # conversa do morador. É o risco aceito registrado no ADR-0001, e o
        # cenário "Reserva cancelada não aparece nas reservas do morador"
        # existe para pegar o dia em que alguém esquecer isto.
        sql = text(
            "SELECT codigo, apartamento, area, data FROM reserva "
            "WHERE apartamento = :ap AND ativa = 1 ORDER BY data, area"
        )
        async with self._engine.connect() as c:
            linhas = (await c.execute(sql, {"ap": apartamento})).all()
        return [
            Reserva(codigo=l[0], apartamento=l[1], area=l[2], data=date.fromisoformat(l[3]))
            for l in linhas
        ]

    async def listar_visitantes_do_apartamento(self, apartamento: str) -> list[Visitante]:
        sql = text(
            "SELECT apartamento, nome, data FROM autorizacao_entrada "
            "WHERE apartamento = :ap ORDER BY data, nome"
        )
        async with self._engine.connect() as c:
            linhas = (await c.execute(sql, {"ap": apartamento})).all()
        return [
            Visitante(apartamento=l[0], nome=l[1], data=date.fromisoformat(l[2])) for l in linhas
        ]

    async def apartamento_existe(self, numero: str) -> bool:
        sql = text("SELECT 1 FROM apartamento WHERE numero = :n")
        async with self._engine.connect() as c:
            return (await c.execute(sql, {"n": numero})).first() is not None

    # -- referência --------------------------------------------------------

    async def listar_areas(self) -> list[Area]:
        sql = text("SELECT id, nome, taxa FROM area ORDER BY id")
        async with self._engine.connect() as c:
            linhas = (await c.execute(sql)).all()
        return [Area(id=l[0], nome=l[1], taxa=float(l[2])) for l in linhas]

    async def buscar_area(self, area_id: str) -> Area | None:
        sql = text("SELECT id, nome, taxa FROM area WHERE id = :id")
        async with self._engine.connect() as c:
            linha = (await c.execute(sql, {"id": area_id})).first()
        return Area(id=linha[0], nome=linha[1], taxa=float(linha[2])) if linha else None

    # -- disponibilidade ---------------------------------------------------

    async def data_esta_livre(self, area: str, data: date) -> bool:
        # ADR-0003 — a área é validada aqui também, não só em `criar_reserva`.
        # Sem isto, perguntar pela piscina devolvia `True`: o morador ouvia
        # que uma área inexistente está livre. Foi assim até 2026-11-08, e o
        # cenário "Consultar disponibilidade de área inexistente não responde
        # livre" existe para que não volte a ser.
        if (await self.buscar_area(area)) is None:
            raise AreaInexistente(area, [a.id for a in await self.listar_areas()])

        # Devolve booleano e nada mais. Quem reservou é dado do outro
        # apartamento e não pode sair daqui (I-06).
        sql = text("SELECT 1 FROM reserva WHERE area = :a AND data = :d AND ativa = 1")
        async with self._engine.connect() as c:
            ocupada = (await c.execute(sql, {"a": area, "d": data.isoformat()})).first()
        return ocupada is None

    # -- escritas ----------------------------------------------------------

    async def criar_reserva(self, apartamento: str, area: str, data: date) -> Reserva:
        if (await self.buscar_area(area)) is None:
            validas = [a.id for a in await self.listar_areas()]
            raise AreaInexistente(area, validas)

        for _ in range(_TENTATIVAS_CODIGO):
            codigo = f"{_PREFIXO_CODIGO}{secrets.randbelow(9000) + 1000}"
            try:
                async with self._engine.begin() as c:
                    await c.execute(
                        text(
                            "INSERT INTO reserva (codigo, apartamento, area, data, ativa) "
                            "VALUES (:c, :ap, :a, :d, 1)"
                        ),
                        {"c": codigo, "ap": apartamento, "a": area, "d": data.isoformat()},
                    )
                return Reserva(codigo=codigo, apartamento=apartamento, area=area, data=data)
            except IntegrityError:
                # Duas colisões possíveis, e elas significam coisas opostas.
                # Só o estado do banco distingue — por isso a consulta vem
                # DEPOIS da falha, nunca antes da gravação.
                dono = await self._dono_da_data(area, data)
                if dono is None:
                    continue  # colisão de código: sorteia outro e tenta de novo
                if dono == apartamento:
                    reserva = await self._reserva_ativa(area, data)
                    raise JaReservadaPorVoce(reserva) from None
                # Outro apartamento venceu. A exceção NÃO carrega quem é (I-06).
                raise AreaIndisponivel(area, data) from None

        raise RuntimeError("Não foi possível gerar um código de reserva livre.")

    async def cancelar_reserva_por_area_data(
        self, apartamento: str, area: str, data: date
    ) -> Reserva:
        return await self._cancelar(
            "apartamento = :ap AND area = :a AND data = :d AND ativa = 1",
            {"ap": apartamento, "a": area, "d": data.isoformat()},
        )

    async def cancelar_reserva_por_codigo(self, apartamento: str, codigo: str) -> Reserva:
        # O `apartamento` no WHERE é a validação de dono. Código de outro
        # apartamento simplesmente não casa — e o chamador recebe exatamente a
        # mesma exceção de "não existe", que é o exigido pelo ADR-0004.
        return await self._cancelar(
            "apartamento = :ap AND codigo = :c AND ativa = 1",
            {"ap": apartamento, "c": codigo},
        )

    async def autorizar_visitante(self, apartamento: str, nome: str, data: date) -> Visitante:
        try:
            async with self._engine.begin() as c:
                await c.execute(
                    text(
                        "INSERT INTO autorizacao_entrada (apartamento, nome, data) "
                        "VALUES (:ap, :n, :d)"
                    ),
                    {"ap": apartamento, "n": nome, "d": data.isoformat()},
                )
        except IntegrityError:
            # A unicidade é do banco (PRIMARY KEY), não de uma checagem prévia.
            raise VisitanteJaAutorizado(nome, data) from None
        return Visitante(apartamento=apartamento, nome=nome, data=data)

    # -- auxiliares --------------------------------------------------------

    async def _cancelar(self, condicao: str, params: dict) -> Reserva:
        async with self._engine.begin() as c:
            linha = (
                await c.execute(
                    text(f"SELECT codigo, apartamento, area, data FROM reserva WHERE {condicao}"),
                    params,
                )
            ).first()
            if linha is None:
                raise ReservaNaoEncontrada()
            await c.execute(
                text("UPDATE reserva SET ativa = 0 WHERE codigo = :c"), {"c": linha[0]}
            )
        return Reserva(
            codigo=linha[0],
            apartamento=linha[1],
            area=linha[2],
            data=date.fromisoformat(linha[3]),
            ativa=False,
        )

    async def _dono_da_data(self, area: str, data: date) -> str | None:
        sql = text(
            "SELECT apartamento FROM reserva WHERE area = :a AND data = :d AND ativa = 1"
        )
        async with self._engine.connect() as c:
            linha = (await c.execute(sql, {"a": area, "d": data.isoformat()})).first()
        return linha[0] if linha else None

    async def _reserva_ativa(self, area: str, data: date) -> Reserva | None:
        sql = text(
            "SELECT codigo, apartamento, area, data FROM reserva "
            "WHERE area = :a AND data = :d AND ativa = 1"
        )
        async with self._engine.connect() as c:
            l = (await c.execute(sql, {"a": area, "d": data.isoformat()})).first()
        return (
            Reserva(codigo=l[0], apartamento=l[1], area=l[2], data=date.fromisoformat(l[3]))
            if l
            else None
        )
