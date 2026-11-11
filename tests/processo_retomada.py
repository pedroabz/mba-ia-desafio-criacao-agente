"""Harness de duas fases para provar a retomada da confirmação (ADR-0014, P1).

Este módulo é rodado como **subprocesso**, duas vezes, pelo cenário
`A retomada da confirmação funciona com sessão em Postgres`. Processos
separados não são capricho de teste: é a única forma de provar que a pendência
vive no banco e não na memória do processo que a criou.

    python -m tests.processo_retomada pendencia <url-postgres> <schema>
    python -m tests.processo_retomada aprovar   <url-postgres> <schema> <sid> <cid>

Cada fase imprime uma linha JSON na última linha da saída.

**Não precisa de chave de API.** O modelo é roteirizado: o que está sob
medição é a maquinaria de confirmação do ADK, não a capacidade do Gemini.

⚠️ A ARMADILHA QUE DERRUBOU A PRIMEIRA VERSÃO: o retrato de taxas do portão
(ADR-0013) precisa ser carregado **depois** do seed. Com a tabela de áreas
vazia, `taxas.get(area, 0.0) > 0` devolve False, a reserva executa SEM
confirmação e o harness relata "não houve pendência" — que parece achado do
ADK e é bug do harness. A asserção em `montar` existe para isso nunca mais
passar calado.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import AsyncGenerator

from google.adk.agents.llm_agent import LlmAgent
from google.adk.apps.app import App
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types

from app.agentes.ferramentas.reservas import criar_ferramentas_de_reserva
from app.agentes.portao import carregar_taxas, portao_de_reserva
from app.infra.banco import aplicar_schema, criar_engine
from app.infra.repositorio_postgres import RepositorioPostgres
from app.infra.seed import semear

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados"

APP = "aurora-retomada"
APARTAMENTO = "101"
# Salão tem taxa 150 (`dados/areas.json`), então passa pelo portão. A quadra,
# com taxa 0, não passaria — e o cenário não provaria nada.
AREA = "salao-de-festas"
DATA = "2030-05-20"


class ModeloRoteirizado(BaseLlm):
    """Pede `criar_reserva` na primeira chamada; depois só escreve texto."""

    model: str = "roteirizado"
    chamadas: int = 0

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        self.chamadas += 1
        if self.chamadas == 1:
            yield LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            function_call=types.FunctionCall(
                                id="fc-criar-1",
                                name="criar_reserva",
                                args={"area": AREA, "data": DATA},
                            )
                        )
                    ],
                )
            )
            return
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text="Pronto.")])
        )


async def montar(url_postgres: str, schema: str):
    """Monta runner e serviço de sessão. Idêntico nas duas fases, de propósito.

    A fase 2 reconstrói tudo do zero, sem herdar nada da fase 1 — é isso que
    faz o teste medir a persistência em vez da memória.
    """
    aplicar_schema(url_postgres, schema=schema)
    engine = criar_engine(url_postgres, schema=schema)
    repositorio = RepositorioPostgres(engine)

    # Semear ANTES de carregar as taxas — ver a armadilha no topo do módulo.
    # Semear nas duas fases também garante que a reserva do cenário só possa
    # existir se a aprovação a tiver criado.
    await semear(engine, DADOS)
    taxas = await carregar_taxas(repositorio)
    assert taxas.get(AREA, 0.0) > 0, (
        f"portão inócuo: a taxa de {AREA} é {taxas.get(AREA)!r}. "
        "Sem taxa > 0 não há confirmação, e o cenário passaria sem provar nada."
    )

    agente = LlmAgent(
        name="reservas",
        model=ModeloRoteirizado(),
        instruction="Atende pedidos de reserva.",
        tools=criar_ferramentas_de_reserva(repositorio, portao_de_reserva(taxas)),
    )
    # NullPool pelo mesmo motivo de `criar_engine` (ADR-0014): o pool do ADK
    # prende a conexão ao loop que a abriu.
    from sqlalchemy.pool import NullPool

    servico = DatabaseSessionService(db_url=url_postgres, poolclass=NullPool)
    runner = Runner(app=App(name=APP, root_agent=agente), session_service=servico)
    return runner, servico, repositorio, engine


async def _reservas_do_cenario(repositorio) -> list:
    reservas = await repositorio.listar_reservas_do_apartamento(APARTAMENTO)
    return [r for r in reservas if r.area == AREA and r.data.isoformat() == DATA]


async def fase_pendencia(url: str, schema: str) -> dict:
    """Pede a reserva e para na pendência. Nada deve ter sido gravado."""
    runner, servico, repositorio, engine = await montar(url, schema)
    sessao = await servico.create_session(
        app_name=APP, user_id=APARTAMENTO, state={"apartamento": APARTAMENTO}
    )

    confirmacao_id = None
    async for evento in runner.run_async(
        user_id=APARTAMENTO,
        session_id=sessao.id,
        new_message=types.Content(
            role="user", parts=[types.Part(text=f"reserve o salão em {DATA}")]
        ),
    ):
        for fc in evento.get_function_calls():
            if fc.name == "adk_request_confirmation":
                confirmacao_id = fc.id

    reservas = await _reservas_do_cenario(repositorio)
    await engine.dispose()
    return {
        "session_id": sessao.id,
        "confirmacao_id": confirmacao_id,
        "reservas_antes_de_aprovar": len(reservas),
    }


async def fase_aprovar(url: str, schema: str, session_id: str, conf_id: str) -> dict:
    """Aprova num processo que nunca viu a sessão da fase 1."""
    runner, _servico, repositorio, engine = await montar(url, schema)

    # R5 do spike R1: a aprovação é um `FunctionResponse` autorado por "user",
    # com o nome `adk_request_confirmation` e o id da chamada de confirmação.
    # NÃO é uma mensagem de texto — reusar o caminho de texto não retoma nada.
    aprovacao = types.Content(
        role="user",
        parts=[
            types.Part(
                function_response=types.FunctionResponse(
                    id=conf_id,
                    name="adk_request_confirmation",
                    response={"confirmed": True},
                )
            )
        ],
    )

    async for _evento in runner.run_async(
        user_id=APARTAMENTO, session_id=session_id, new_message=aprovacao
    ):
        pass

    reservas = await _reservas_do_cenario(repositorio)
    await engine.dispose()
    return {
        "reservas_depois_de_aprovar": len(reservas),
        "codigos": [r.codigo for r in reservas],
    }


def main() -> None:
    fase, url, schema = sys.argv[1], sys.argv[2], sys.argv[3]
    if fase == "pendencia":
        resultado = asyncio.run(fase_pendencia(url, schema))
    elif fase == "aprovar":
        resultado = asyncio.run(fase_aprovar(url, schema, sys.argv[4], sys.argv[5]))
    else:
        raise SystemExit(f"fase desconhecida: {fase}")
    print(json.dumps(resultado))


if __name__ == "__main__":
    main()
