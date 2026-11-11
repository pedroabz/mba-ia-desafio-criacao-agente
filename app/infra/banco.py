"""Schema do Postgres e criação do engine.

Este arquivo é onde três invariantes do domínio deixam de depender de
disciplina de código e passam a ser impostos pelo banco. Mexer aqui sem ler os
ADRs correspondentes quebra garantias que nenhum teste de caminho feliz pega.

  * `UNIQUE (codigo)` sobre a tabela inteira ............. I-03 · ADR-0001
  * `UNIQUE (area, data) WHERE ativa = 1` ............... I-01 · ADR-0001
  * `PRIMARY KEY (apartamento, nome, data)` ............. ADR-0005

**Postgres, não SQLite** (ADR-0014). Um banco para tudo: domínio, sessão do
ADK (Garantia 3) e os vetores do regulamento (ADR-0015, ADR-0020). O que a
troca tirou de graça: o `PRAGMA foreign_keys` que o SQLite exigia por conexão
não existe aqui, porque o Postgres sempre impõe `REFERENCES`. O índice parcial,
que no SQLite era um recurso a conferir, é nativo.
"""

from __future__ import annotations

import asyncio
import concurrent.futures

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

# Schema do Postgres onde a aplicação mora. A suíte usa um schema próprio por
# teste (ver `tests/conftest.py`), que é o isolamento que o plano 1.4 nomeia
# como risco do P2: sem ele, um caso enxerga a reserva do outro e a suíte fica
# intermitente — pior que vermelha.
SCHEMA_PADRAO = "public"

# A dimensão do vetor é do ADR-0020 e vive em `app/infra/embeddings.py`. É
# importada aqui, e não repetida, porque schema e chamada ao modelo PRECISAM
# concordar: se divergirem, o banco recusa toda gravação — e com dois números
# literais nada impede a divergência.
from app.infra.embeddings import DIMENSOES as DIMENSOES_EMBEDDING  # noqa: E402

# A extensão `vector` vive no `public` de propósito, mesmo quando as tabelas
# estão num schema de teste: o tipo precisa ser alcançável por qualquer
# `search_path` que termine em `public`. Criá-la dentro de cada schema de teste
# multiplicaria extensão por teste sem necessidade.
DDL_EXTENSAO: tuple[str, ...] = (
    "CREATE EXTENSION IF NOT EXISTS vector",
)

# Uma entrada por comando. Deliberadamente uma lista, e não um script único
# separado por `;`: qualquer parsing caseiro quebra no primeiro ponto e vírgula
# que aparecer dentro de um comentário — já quebrou uma vez aqui.
DDL: tuple[str, ...] = (
    # Referência: semeados de dados/*.json, nunca alterados pelo assistente.
    # ADR-0002 — a tabela é a fonte de verdade em tempo de execução.
    """
    CREATE TABLE IF NOT EXISTS apartamento (
        numero  TEXT PRIMARY KEY,
        morador TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS area (
        id   TEXT PRIMARY KEY,
        nome TEXT NOT NULL,
        taxa DOUBLE PRECISION NOT NULL
    )
    """,
    # ADR-0001 — soft delete. Cancelar faz `ativa = 0` e a linha PERMANECE.
    #
    # `codigo` é PRIMARY KEY, ou seja, único sobre a tabela INTEIRA — ativas e
    # canceladas. É o que garante que um código nunca se repita "inclusive de
    # uma reserva cancelada" (regra 5 do enunciado). Por isso a linha cancelada
    # não pode sumir: apagá-la apagaria o conhecimento de que o código existiu.
    #
    # `data` segue TEXT, como era no SQLite, e `ativa` segue INTEGER 0/1. Não é
    # descuido: é o que mantém a migração sem reescrever uma linha do
    # repositório, que compara `data` com `date.isoformat()` e filtra
    # `ativa = 1` em sete lugares. Trocar para DATE e BOOLEAN é melhoria
    # legítima, e é mudança de outro passo — não deste.
    """
    CREATE TABLE IF NOT EXISTS reserva (
        codigo      TEXT PRIMARY KEY,
        apartamento TEXT NOT NULL REFERENCES apartamento(numero),
        area        TEXT NOT NULL REFERENCES area(id),
        data        TEXT NOT NULL,
        ativa       INTEGER NOT NULL DEFAULT 1 CHECK (ativa IN (0, 1))
    )
    """,
    # I-01: uma reserva ATIVA por área e data.
    #
    # ⚠️ `WHERE ativa = 1` não é otimização, é a regra. Sem a cláusula parcial o
    # índice cobriria também as canceladas, e uma data já cancelada ficaria
    # bloqueada para sempre — falha que nenhum teste de reserva comum detecta.
    # O cenário "Data liberada por cancelamento aceita nova reserva" existe
    # exatamente para pegar isso.
    """
    CREATE UNIQUE INDEX IF NOT EXISTS ix_reserva_area_data_ativa
        ON reserva (area, data) WHERE ativa = 1
    """,
    # ADR-0005 — a segunda autorização para a mesma tripla é recusada pelo
    # banco. A chave de negócio é (apartamento, nome, data) porque é só isso
    # que o enunciado define como conteúdo de uma autorização (regra 3).
    """
    CREATE TABLE IF NOT EXISTS autorizacao_entrada (
        apartamento TEXT NOT NULL REFERENCES apartamento(numero),
        nome        TEXT NOT NULL,
        data        TEXT NOT NULL,
        PRIMARY KEY (apartamento, nome, data)
    )
    """,
    # ADR-0015 (recuperação semântica) + ADR-0016 (a unidade é o ARTIGO, não o
    # capítulo) + ADR-0020 (o modelo e a dimensão).
    #
    # ⚠️ `vector(768)` é dimensão FIXA, e o banco recusa um vetor de outro
    # tamanho — é o que torna a `M-6` imposta por código em vez de disciplina.
    # 768 e não o padrão de 3.072 porque acima de 2.000 o `pgvector` não aceita
    # índice `hnsw` nem `ivfflat`: para 96 artigos a varredura exata é
    # instantânea, então o que 768 preserva é a OPÇÃO do índice, não
    # desempenho hoje.
    #
    # Trocar de modelo de embedding exige REGERAR todos os vetores: os espaços
    # são incompatíveis entre modelos, e um vetor do `-001` comparado a um do
    # `-2` produz proximidade sem sentido, sem erro nenhum.
    f"""
    CREATE TABLE IF NOT EXISTS regulamento_trecho (
        titulo    TEXT PRIMARY KEY,
        capitulo  TEXT NOT NULL,
        texto     TEXT NOT NULL,
        embedding vector({DIMENSOES_EMBEDDING}) NOT NULL
    )
    """,
    # `rotas/D-02` — de que apartamento é uma conversa.
    #
    # O problema que esta tabela resolve: o ADK guarda cada conversa debaixo de
    # (aplicação, USUÁRIO, id), e medimos que ele separa de verdade — com o
    # usuário errado, devolve nada. Mas a URL da API só traz o `session_id`.
    # Sem esta tabela, a rota não consegue nem abrir a conversa.
    #
    # ⚠️ **Sem `REFERENCES apartamento(numero)`, de propósito.** O seed de
    # `dados/` apaga e regrava as tabelas de referência inteiras (ADR-0002);
    # uma chave estrangeira daqui faria `DELETE FROM apartamento` falhar
    # enquanto houvesse conversa aberta. O apartamento já é validado na criação
    # da sessão, que é o único lugar que escreve aqui.
    #
    # ⚠️ **A restauração NÃO apaga esta tabela.** O enunciado deixa a escolha
    # livre ("se ele também apaga as sessões, é decisão sua"), e restaurar é
    # voltar os DADOS DO CONDOMÍNIO ao estado inicial — uma conversa não é dado
    # do condomínio. Apagar aqui e não poder apagar as tabelas do ADK deixaria
    # os dois registros divergentes.
    """
    CREATE TABLE IF NOT EXISTS conversa (
        session_id  TEXT PRIMARY KEY,
        apartamento TEXT NOT NULL,
        criada_em   TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
)


class BancoInacessivel(RuntimeError):
    """O Postgres não respondeu na URL configurada.

    Existe como tipo próprio para a subida da aplicação poder dizer **o que
    fazer** em vez de empilhar rastro de pilha de driver. O passo 1 do roteiro
    do avaliador roda num clone limpo: se o `docker compose` não subiu, a
    mensagem é a única coisa entre ele e desistir.
    """


MENSAGEM_INACESSIVEL = (
    "Não consegui falar com o Postgres em {url}.\n"
    "\n"
    "Suba o banco antes de rodar a aplicação:\n"
    "    docker compose up -d --wait\n"
    "\n"
    "Se o banco estiver em outro endereço, aponte a variável URL_BANCO para ele."
)


def criar_engine(url: str, *, schema: str = SCHEMA_PADRAO) -> AsyncEngine:
    """Cria o engine async, fixando o `search_path` por conexão.

    O `search_path` termina sempre em `public` porque é lá que a extensão
    `vector` mora — sem isso, uma tabela com coluna `vector(768)` num schema de
    teste não encontraria o tipo.

    ⚠️ **`NullPool` não é desleixo, é o que faz a suíte funcionar.** Uma
    conexão do `asyncpg` fica presa ao event loop que a abriu, e o pool a
    reaproveita; os passos do pytest-bdd são síncronos e cada um roda a sua
    corrotina num loop NOVO. Com pool, o segundo passo de um cenário pega uma
    conexão de outro loop e morre com `got Future attached to a different
    loop` — foi exatamente o que aconteceu ao migrar, em 29 cenários de uma
    vez. Com SQLite o problema não existia, e por isso o código anterior não
    precisava disto.

    O custo é uma conexão TCP nova por operação. No volume deste projeto — um
    avaliador percorrendo 15 passos — é irrelevante, e em troca desaparece uma
    classe inteira de acoplamento entre engine e loop.
    """
    engine = create_async_engine(url, future=True, poolclass=NullPool)

    if schema != SCHEMA_PADRAO:
        @event.listens_for(engine.sync_engine, "connect")
        def _fixar_search_path(conexao, _registro) -> None:  # noqa: ANN001
            cursor = conexao.cursor()
            cursor.execute(f'SET search_path TO "{schema}", public')
            cursor.close()

    return engine


def executar_sincrono(corrotina):
    """Roda uma corrotina de uma thread própria, com loop próprio.

    `aplicar_schema` é síncrona de propósito (ver a docstring dela), mas o
    driver do Postgres é async-only. Uma thread com loop próprio funciona tanto
    quando não há loop rodando quanto quando há — o que `asyncio.run` direto
    não faz, e a diferença apareceria só em quem chamasse de dentro de código
    assíncrono.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, corrotina).result()


def aplicar_schema(url: str, *, schema: str = SCHEMA_PADRAO) -> None:
    """Cria a extensão, o schema e as tabelas. Idempotente — tudo `IF NOT EXISTS`.

    ADR-0006 — tanto a aplicação (ao subir) quanto o comando de restauração
    chamam esta função. É a idempotência que permite dois pontos de entrada
    criarem estrutura sem conflito, e é por isso que **nenhum dos dois define
    DDL próprio**: os dois chamam daqui. Schema escrito num segundo lugar
    diverge em silêncio.

    Deliberadamente **síncrona**. Criar schema é operação estrutural de uma vez
    só, e nada nela se beneficia de ser async — enquanto exigir um event loop
    obrigaria `criar_app()` a ser assíncrona ou a depender do `lifespan`, que
    não dispara em clientes ASGI de teste.

    ⚠️ `CREATE TABLE IF NOT EXISTS` **não altera tabela existente**. Enquanto
    este projeto não tiver migração de schema, tudo bem; no dia em que tiver,
    subir sobre um schema velho passaria sem reclamar. Risco registrado no
    ADR-0006.

    Raises:
        BancoInacessivel: quando o Postgres não responde, com a mensagem que
            diz qual comando sobe o banco.
    """

    async def aplicar() -> None:
        engine = create_async_engine(url, future=True)
        try:
            async with engine.begin() as conexao:
                for comando in DDL_EXTENSAO:
                    await conexao.execute(text(comando))
                if schema != SCHEMA_PADRAO:
                    await conexao.execute(
                        text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
                    )
                await conexao.execute(text(f'SET search_path TO "{schema}", public'))
                for comando in DDL:
                    await conexao.execute(text(comando))
        finally:
            await engine.dispose()

    try:
        executar_sincrono(aplicar())
    except BancoInacessivel:
        raise
    except Exception as erro:  # noqa: BLE001
        # Qualquer falha de conexão vira a mesma recusa legível. Não
        # distinguimos "host errado" de "banco não subiu" porque a ação do
        # leitor é a mesma, e um `except` estreito aqui deixaria passar o
        # rastro de pilha que esta função existe para evitar.
        if _e_falha_de_conexao(erro):
            raise BancoInacessivel(MENSAGEM_INACESSIVEL.format(url=url)) from None
        raise


def _e_falha_de_conexao(erro: BaseException) -> bool:
    """Distingue "não consegui conectar" de erro de DDL.

    Um erro de DDL é bug nosso e precisa subir com rastro; falha de conexão é
    ambiente e precisa de instrução. Olhamos a cadeia de causas porque o
    SQLAlchemy embrulha o erro do driver.
    """
    from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError

    atual: BaseException | None = erro
    while atual is not None:
        if isinstance(atual, (OperationalError, InterfaceError)):
            return True
        if isinstance(atual, ConnectionError | OSError):
            return True
        # asyncpg levanta estas sem herdar de OSError.
        if type(atual).__name__ in {
            "ConnectionDoesNotExistError",
            "CannotConnectNowError",
            "InvalidCatalogNameError",
            "InvalidPasswordError",
            "ConnectionRefusedError",
        }:
            return True
        if isinstance(atual, DBAPIError) and atual.connection_invalidated:
            return True
        atual = atual.__cause__ or atual.__context__
    return False


def remover_schema(url: str, schema: str) -> None:
    """Apaga um schema inteiro. Existe para o descarte entre testes."""

    async def remover() -> None:
        engine = create_async_engine(url, future=True)
        try:
            async with engine.begin() as conexao:
                await conexao.execute(
                    text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
                )
        finally:
            await engine.dispose()

    executar_sincrono(remover())
