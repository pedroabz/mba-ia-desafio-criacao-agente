"""Ponto de entrada da API.

Subida:

    uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

(o comando definitivo de subida, documentado no README de entrega, é decisão
da task 1.2.)
"""

from __future__ import annotations

from app.api.aplicacao import criar_app

app = criar_app()
