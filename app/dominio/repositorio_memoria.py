"""Implementação TEMPORÁRIA de `RepositorioCondominio`, em memória.

⚠️  TEMPORÁRIA DE PROPÓSITO. A task 1.3 do `TODO.md` substitui esta classe por
uma implementação em Postgres, e nenhuma rota precisa mudar por isso — é o motivo
de a seam `RepositorioCondominio` existir.

O que ela NÃO resolve (e por isso não pode ficar):
  * Garantia 3 (nada se perde no reinício): memória morre com o processo.
  * Garantia 5 (dois moradores, uma reserva): exclusividade no instante da
    gravação pede índice único do banco.

O que ela JÁ resolve, e que a 1.3 deve preservar:
  * A semeadura a partir de `dados/*.json` espelha a semântica do futuro
    comando de restauração: lê o estado inicial do condomínio e o carrega como
    estado corrente.

REGRA ABSOLUTA: nunca escrever em `dados/`. É critério de aceite (passo 15 do
fluxo do avaliador) que esses arquivos fiquem idênticos aos do repositório
base. Aqui os arquivos são apenas lidos; tudo é copiado para memória e só a
cópia é mutada.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date
from pathlib import Path

from app.dominio.modelos import Apartamento, Area, Reserva, Visitante


class DadosIniciais:
    """Snapshot do estado inicial do condomínio, lido de `dados/*.json`."""

    __slots__ = ("apartamentos", "areas", "reservas", "visitantes")

    def __init__(
        self,
        apartamentos: list[Apartamento],
        areas: list[Area],
        reservas: list[Reserva],
        visitantes: list[Visitante],
    ) -> None:
        self.apartamentos = apartamentos
        self.areas = areas
        self.reservas = reservas
        self.visitantes = visitantes


def carregar_dados_iniciais(diretorio: Path) -> DadosIniciais:
    """Lê (somente lê!) os JSON de `dados/` e devolve objetos de domínio.

    Os modelos de domínio são `frozen`, então o resultado pode ser compartilhado
    sem medo: quem quiser mudar o estado monta listas novas.
    """

    def _ler(nome: str) -> list[dict]:
        caminho = diretorio / nome
        with caminho.open(encoding="utf-8") as arquivo:
            return json.load(arquivo)

    return DadosIniciais(
        apartamentos=[
            Apartamento(numero=str(item["numero"]), morador=item["morador"])
            for item in _ler("apartamentos.json")
        ],
        areas=[
            Area(id=item["id"], nome=item["nome"], taxa=float(item["taxa"]))
            for item in _ler("areas.json")
        ],
        reservas=[
            Reserva(
                codigo=item["codigo"],
                apartamento=str(item["apartamento"]),
                area=item["area"],
                data=date.fromisoformat(item["data"]),
            )
            for item in _ler("reservas.json")
        ],
        visitantes=[
            Visitante(
                apartamento=str(item["apartamento"]),
                nome=item["nome"],
                data=date.fromisoformat(item["data"]),
            )
            for item in _ler("visitantes.json")
        ],
    )


class RepositorioEmMemoria:
    """Repositório do condomínio guardado em listas na memória do processo.

    Implementa `app.dominio.repositorio.RepositorioCondominio`.
    """

    def __init__(self, dados: DadosIniciais) -> None:
        # Cópias próprias: mutar o repositório não pode refletir no snapshot
        # inicial (que é o equivalente em memória do conteúdo de `dados/`).
        self._apartamentos = {ap.numero: ap for ap in dados.apartamentos}
        self._areas = {area.id: area for area in dados.areas}
        self._reservas: list[Reserva] = list(dados.reservas)
        self._visitantes: list[Visitante] = list(dados.visitantes)
        # Serializa as mutações futuras (Fase 2). Não protege contra nada
        # entre processos — outra razão pela qual a 1.3 precisa de banco.
        self._trava = asyncio.Lock()

    # -- leituras usadas pelas rotas de verificação -------------------------

    async def listar_reservas_do_apartamento(self, apartamento: str) -> list[Reserva]:
        return [reserva for reserva in self._reservas if reserva.apartamento == apartamento]

    async def listar_visitantes_do_apartamento(self, apartamento: str) -> list[Visitante]:
        return [
            visitante for visitante in self._visitantes if visitante.apartamento == apartamento
        ]

    async def apartamento_existe(self, numero: str) -> bool:
        return numero in self._apartamentos
