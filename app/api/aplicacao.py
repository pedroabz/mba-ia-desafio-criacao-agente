"""App factory do FastAPI.

É aqui, e só aqui, que as interfaces do domínio ganham uma implementação
concreta. As rotas nunca importam uma implementação: elas pedem
`RepositorioCondominio` e `ServicoSessao` por injeção de dependência.

Consequência prática: o armazenamento (hoje Postgres, ADR-0014) e a Fase 2
(`SessionService` do ADK) mexem apenas nas duas linhas de montagem abaixo.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import rotas_apartamentos, rotas_sessoes
from app.api.erros import registrar_tratadores
from app.config import obter_configuracao
from app.dominio.repositorio import RepositorioCondominio
from google.adk.sessions import DatabaseSessionService
from sqlalchemy.pool import NullPool

from app.dominio.sessao import ServicoSessao
from app.infra.banco import (
    SCHEMA_PADRAO,
    aplicar_schema,
    criar_engine,
    executar_sincrono,
)
from app.infra.repositorio_postgres import RepositorioPostgres
from app.infra.sessao_adk import ServicoSessaoADK


def criar_app(
    *,
    repositorio: RepositorioCondominio | None = None,
    servico_sessao: ServicoSessao | None = None,
    url_banco: str | None = None,
    schema: str = SCHEMA_PADRAO,
    modelo=None,
) -> FastAPI:
    """Monta a aplicação.

    Os parâmetros existem para teste e para a troca de implementação: passar
    um `repositorio` ou um `servico_sessao` substitui a implementação padrão
    sem tocar em nenhuma rota. O `schema` existe para a suíte dar um schema
    próprio a cada caso — ver o risco de isolamento no plano 1.4.
    """
    configuracao = obter_configuracao()

    if repositorio is None:
        # ADR-0006 — a aplicação aplica o schema ao subir. O DDL é idempotente,
        # então subir sobre um banco existente não altera nada; e subir num
        # clone limpo funciona sem depender de a restauração ter rodado antes.
        #
        # Síncrono de propósito: mantém `criar_app()` síncrona e independente
        # do `lifespan`, que não dispara em clientes ASGI de teste. Levanta
        # `BancoInacessivel` com instrução quando o Postgres não está no ar
        # (ADR-0014) — o passo 1 do avaliador roda num clone limpo.
        url = url_banco or configuracao.url_banco
        aplicar_schema(url, schema=schema)
        repositorio = RepositorioPostgres(criar_engine(url, schema=schema))

    if servico_sessao is None:
        # Garantia 3, a parte da CONVERSA. Até aqui a aplicação montava um
        # `ServicoSessaoEmMemoria` e os eventos morriam com o processo — os
        # dados sobreviviam (ADR-0014), a conversa não. O
        # `DatabaseSessionService` sobre o mesmo Postgres fecha isso, e que ele
        # não quebra a retomada da confirmação foi provado em dois processos
        # separados (`tests/processo_retomada.py`, P1 do plano 1.4).
        url = url_banco or configuracao.url_banco
        # ⚠️ `poolclass=NullPool` TAMBÉM aqui, e pelo mesmo motivo do
        # ADR-0014: conexão do `asyncpg` fica presa ao event loop que a abriu.
        # O `DatabaseSessionService` monta o engine DELE, com o pool padrão —
        # e isso quebrou em três lugares diferentes deste projeto antes de
        # alguém ligar os pontos: nos passos do pytest-bdd, no `TestClient`
        # (que monta um portal por requisição) e no harness de dois processos.
        #
        # O custo é uma conexão TCP nova por operação de sessão. No volume
        # deste projeto — um avaliador percorrendo 15 passos — é irrelevante.
        servico_sessao = ServicoSessaoADK(
            DatabaseSessionService(db_url=url, poolclass=NullPool),
            criar_engine(url, schema=schema),
        )

    @asynccontextmanager
    async def ciclo_de_vida(aplicacao: FastAPI):
        # Reservado para o Runner/App do ADK (Fase 2). O engine do banco NÃO
        # é aberto aqui: ver comentário abaixo sobre o state.
        yield

    aplicacao = FastAPI(
        title="Residencial Aurora — assistente do condomínio",
        description=(
            "API do assistente do Residencial Aurora. As rotas de verificação "
            "leem os dados do condomínio direto, sem passar pelo modelo."
        ),
        version="0.1.0",
        lifespan=ciclo_de_vida,
    )

    # As seams entram no state na CONSTRUÇÃO, não no lifespan: assim a app
    # fica utilizável sem que o ciclo de vida tenha rodado (é o caso de
    # clientes ASGI em teste, que não disparam startup/shutdown).
    aplicacao.state.repositorio = repositorio
    aplicacao.state.servico_sessao = servico_sessao

    # A conversa só é montada quando há um serviço de sessão do ADK: é ele que
    # o `Runner` precisa. Um `servico_sessao` injetado por teste (um falso, por
    # exemplo) deixa as rotas de conversa indisponíveis em vez de montar um
    # runner sobre algo que não é sessão do ADK.
    aplicacao.state.conversa = None
    if isinstance(servico_sessao, ServicoSessaoADK):
        from app.agentes.portao import carregar_taxas
        from app.agentes.principal import criar_agente_principal
        from app.api.conversa import Conversa, construir_runner
        from app.infra.embeddings import EmbeddingGemini
        from app.infra.recuperacao import RecuperadorDeRegulamento

        # ADR-0013 — o retrato das taxas é lido do banco UMA VEZ, aqui na
        # subida. Depois disto o portão de confirmação nunca toca o banco: uma
        # leitura que falhasse no instante da decisão degradaria para "não
        # precisa confirmar", e a Garantia 1 cairia por um erro sem relação
        # com ela.
        taxas = executar_sincrono(carregar_taxas(repositorio))

        url = url_banco or configuracao.url_banco
        recuperador = RecuperadorDeRegulamento(
            criar_engine(url, schema=schema), EmbeddingGemini()
        )
        principal = criar_agente_principal(repositorio, recuperador, taxas, modelo)
        aplicacao.state.conversa = Conversa(
            construir_runner(principal, servico_sessao.servico_adk),
            servico_sessao,
        )

    # ADR-0019 — falha de quota vira `503` com `Retry-After`, e não `200` com
    # resposta vazia (que é o sinal de confirmação pendente). Ver `M-4`.
    registrar_tratadores(aplicacao)

    aplicacao.include_router(rotas_sessoes.roteador)
    aplicacao.include_router(rotas_apartamentos.roteador)

    @aplicacao.get("/saude", tags=["infra"], summary="Checagem de vida da API")
    async def saude() -> dict[str, str]:
        return {"status": "ok"}

    return aplicacao
