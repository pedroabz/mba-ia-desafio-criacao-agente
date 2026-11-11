"""Fatiamento do regulamento interno em unidades de recuperação.

**A unidade é o artigo, não o capítulo** (ADR-0016). O spike 1.4 mediu por quê:
a resposta a *"pode cachorro na quadra?"* está no Art. 56, dentro do Capítulo
VIII (Animais), enquanto o Capítulo VI — que fala da quadra — não menciona
animal nenhuma vez. Recuperar por capítulo erraria, e devolver o capítulo
inteiro violaria a Garantia 4 (*"não pode trazer trechos de capítulos que
tratam de outros assuntos"*).

**O título do capítulo entra no texto que gera o vetor**, também por ADR-0016:
um artigo como *"Art. 22. Funciona de terça a domingo, das 8h às 20h"* não diz
de que coisa ele está falando. Sem o capítulo, o vetor dele fica ambíguo entre
piscina, academia e salão. Com ele, a pergunta "até que horas a piscina
funciona" encosta no lugar certo.

Este módulo não faz I/O e não chama modelo: recebe texto, devolve estrutura. É
o que permite testá-lo sem banco e sem chave de API.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# `## Capítulo IV: Piscina` — o romano e o título são capturados juntos porque
# é assim que eles entram no texto do vetor.
_CAPITULO = re.compile(r"^##\s+(Cap[íi]tulo\s+[IVXLC]+)\s*:\s*(.+?)\s*$")

# `**Art. 22º** texto...` ou `**Art. 1º** texto...`. O número pode vir com `º`,
# com `.` ou sozinho; o que delimita é o começo da linha em negrito.
_ARTIGO = re.compile(r"^\*\*(Art\.\s*\d+\s*[º°\.]?)\*\*\s*(.*)$")


@dataclass(frozen=True)
class TrechoRegulamento:
    """Um artigo do regulamento, com o capítulo a que pertence."""

    titulo: str
    """O identificador do artigo, normalizado: `Art. 22`."""

    capitulo: str
    """O capítulo inteiro, como aparece no documento: `Capítulo IV: Piscina`."""

    texto: str
    """O corpo do artigo, com parágrafos e incisos, sem o título do capítulo."""

    @property
    def texto_para_vetor(self) -> str:
        """O que efetivamente vai ao modelo de embedding.

        O capítulo primeiro, o artigo depois. É a decisão do ADR-0016 em uma
        linha — e é por isso que ela é uma *propriedade* e não uma concatenação
        espalhada por quem chama: um lugar só para mudar, se um dia mudar.
        """
        return f"{self.capitulo}\n\n{self.titulo} {self.texto}"


def _normalizar_titulo(bruto: str) -> str:
    """`Art.  22º` -> `Art. 22`. Um artigo tem um nome só."""
    numero = re.search(r"\d+", bruto)
    return f"Art. {numero.group()}" if numero else bruto.strip()


def fatiar_em_artigos(markdown: str) -> list[TrechoRegulamento]:
    """Parte o regulamento em artigos, preservando o capítulo de cada um.

    O que fecha um artigo é o começo do próximo, ou um capítulo novo, ou o fim
    do documento. Tudo que está no meio — `Parágrafo único`, `§ 1º`, incisos
    `I.`, `II.` — pertence ao artigo e vai junto: são eles que carregam os
    horários e os limites que o morador pergunta.
    """
    trechos: list[TrechoRegulamento] = []
    capitulo = ""
    titulo: str | None = None
    corpo: list[str] = []

    def fechar() -> None:
        if titulo is not None:
            trechos.append(
                TrechoRegulamento(
                    titulo=titulo,
                    capitulo=capitulo,
                    texto="\n".join(corpo).strip(),
                )
            )

    for linha in markdown.splitlines():
        if (achado := _CAPITULO.match(linha)) is not None:
            fechar()
            titulo, corpo = None, []
            capitulo = f"{achado.group(1)}: {achado.group(2)}"
            continue

        if (achado := _ARTIGO.match(linha)) is not None:
            fechar()
            titulo = _normalizar_titulo(achado.group(1))
            corpo = [achado.group(2).strip()]
            continue

        if titulo is not None:
            corpo.append(linha)

    fechar()
    return trechos
