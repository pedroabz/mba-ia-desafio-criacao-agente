#!/usr/bin/env python3
"""Confere que decisões, invariantes e cenários continuam ligados entre si.

**Sai com código != 0 quando algo está órfão.** É de propósito: um índice
escrito à mão apodrece em silêncio, um script que falha não. Rode no mesmo
lugar onde você roda os testes.

O que ele acusa:

  1. ADR sem nenhum cenário apontando para ele — decisão sem verificação.
  2. Cenário apontando para ADR que não existe — ponteiro quebrado, em geral
     depois de renomear ou substituir um ADR.
  3. Invariante I-NN sem nenhum cenário — a regra existe no papel e nada a
     cobra no código.
  4. Cenário `@pendente` — não é erro, mas é contado e listado, para pendência
     nunca virar paisagem.

Uso:
    uv run python scripts/cobertura.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ADRS = RAIZ / "docs" / "adr"
FEATURES = RAIZ / "tests" / "features"
SPIKES = sorted((RAIZ / "docs").glob("spike-*.md"))

RE_ADR_ARQUIVO = re.compile(r"^(\d{4})-")
RE_ADR_CITADO = re.compile(r"ADR-(\d{4})")
RE_INVARIANTE = re.compile(r"\bI-(\d{2})\b")
RE_CENARIO = re.compile(r"^\s*Cen[áa]rio:\s*(.+)$", re.MULTILINE)
# Só a etiqueta de verdade — linha que começa com @ —, nunca a palavra citada
# dentro de um comentário explicativo do próprio arquivo.
RE_PENDENTE = re.compile(r"^\s*@[\w@ ]*\bpendente\b", re.MULTILINE)


def main() -> int:
    if not FEATURES.exists():
        print("✗ tests/features/ não existe — nenhum cenário materializado.")
        return 1

    adrs = {m.group(1) for p in ADRS.glob("*.md") if (m := RE_ADR_ARQUIVO.match(p.name))}
    invariantes = {m for p in SPIKES for m in RE_INVARIANTE.findall(p.read_text())}

    features = list(FEATURES.glob("*.feature"))
    texto = "\n".join(p.read_text() for p in features)
    cenarios = RE_CENARIO.findall(texto)
    pendentes = len(RE_PENDENTE.findall(texto))

    adrs_citados = set(RE_ADR_CITADO.findall(texto))
    invariantes_citados = set(RE_INVARIANTE.findall(texto))

    # Duas classes de problema, com causas bem diferentes. Separá-las importa
    # porque a primeira é defeito e a segunda é obra em andamento — misturar
    # faz o relatório perder sentido no meio do projeto.
    quebrados: list[str] = []  # ponteiro errado: alguém renomeou ou apagou
    descobertos: list[str] = []  # regra sem teste: ainda não foi construída

    for adr in sorted(adrs_citados - adrs):
        quebrados.append(f"cenário cita ADR-{adr}, que não existe em docs/adr/")
    for adr in sorted(adrs - adrs_citados):
        descobertos.append(f"ADR-{adr} não é citado por nenhum cenário — decisão sem verificação")
    for inv in sorted(invariantes - invariantes_citados):
        descobertos.append(f"invariante I-{inv} não tem cenário que o cubra")

    print(f"ADRs .............. {len(adrs)}")
    print(f"invariantes ....... {len(invariantes)}")
    print(f"cenários .......... {len(cenarios)} em {len(features)} arquivo(s)")
    print(f"  pendentes ....... {pendentes}")

    if quebrados:
        print("\nPonteiros quebrados:")
        for p in quebrados:
            print(f"  ✗ {p}")

    if descobertos:
        print("\nSem cobertura:")
        for p in descobertos:
            print(f"  ✗ {p}")

    if quebrados or descobertos:
        print(
            "\nSaindo com erro de propósito. Enquanto houver fase aberta, é esperado"
            "\nque alguns invariantes ainda não tenham cenário — mas isso precisa"
            "\ndoer toda vez, senão vira paisagem e a regra some sem ninguém notar."
        )
        return 1

    print("\n✓ nada órfão, nada descoberto.")
    if pendentes:
        print(f"  ({pendentes} cenário(s) pendente(s) — vermelhos na suíte, como devem ser)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
