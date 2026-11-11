"""Modelos de domínio do condomínio.

Espelham, campo a campo, o formato dos arquivos de `dados/*.json`, que são o
estado inicial do condomínio. São objetos de domínio puros: não sabem nada
sobre HTTP, nem sobre o armazenamento onde estão guardados.

Os modelos de request/response da API vivem em `app/api/esquemas.py` e são
deliberadamente separados destes: o contrato da API **não** expõe todos os
campos do domínio (por exemplo, `Reserva.apartamento` não aparece na resposta
de `GET /apartamentos/{numero}/reservas`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class Apartamento:
    """Um apartamento do condomínio (`dados/apartamentos.json`)."""

    numero: str
    morador: str


@dataclass(frozen=True, slots=True)
class Area:
    """Uma área comum (`dados/areas.json`).

    `taxa` em reais; `0` significa área sem cobrança — é o que decide se
    reservar a área exige confirmação (Garantia 1).
    """

    id: str
    nome: str
    taxa: float

    @property
    def gera_cobranca(self) -> bool:
        """Regra de negócio 2: só taxa maior que zero gera cobrança."""
        return self.taxa > 0


@dataclass(frozen=True, slots=True)
class Reserva:
    """Uma reserva de área comum (`dados/reservas.json`).

    `area` guarda o `id` da área, não o nome. `data` é uma data do calendário
    (serializada como AAAA-MM-DD no contrato da API).

    `ativa` existe por causa do ADR-0001: cancelar **não apaga** a linha, marca
    `ativa = False`. Isso é o que torna possível garantir que um código de
    reserva nunca se repita, "inclusive de uma reserva cancelada" (regra 5 do
    enunciado) — apagar a linha apagaria o conhecimento de que aquele código
    existiu, e a regra viraria inverificável.

    Consequência para quem lê daqui: **toda leitura destinada ao morador filtra
    `ativa = True`**. Uma reserva cancelada que vaze para a conversa é bug.
    """

    codigo: str
    apartamento: str
    area: str
    data: date
    ativa: bool = True


@dataclass(frozen=True, slots=True)
class Visitante:
    """Uma autorização de entrada de visitante (`dados/visitantes.json`).

    Não tem identificador próprio: a chave de negócio é a tripla
    `(apartamento, nome, data)`, porque é isso que o enunciado define como
    conteúdo de uma autorização (regra 3). Ver ADR-0005 — inclusive o risco
    aceito de usar nome como chave.
    """

    apartamento: str
    nome: str
    data: date
