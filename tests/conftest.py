"""Fixtures e implementação dos passos dos cenários `@storage`.

Os cenários vivem em `tests/features/*.feature` e são a fonte de verdade do
comportamento. Este arquivo apenas os liga ao código — se o texto de um cenário
mudar e o passo correspondente sumir, o `pytest` falha na hora, que é o que
impede documento e teste de divergirem em silêncio.

Cenários `@conversa` continuam sem implementação de propósito: eles dependem
dos agentes (Fase 4) e de chave de API. Falham com
`StepDefinitionNotFoundError`, dizendo exatamente qual passo falta.
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest
from pytest_bdd import given, parsers, then, when

from app.dominio.erros import (
    AreaIndisponivel,
    AreaInexistente,
    JaReservadaPorVoce,
    ReservaNaoEncontrada,
    VisitanteJaAutorizado,
)
from app.config import obter_configuracao
from app.infra.banco import aplicar_schema, criar_engine, remover_schema
from app.infra.repositorio_postgres import RepositorioPostgres
from app.infra.seed import semear, semear_regulamento

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados"


_loop_da_suite: asyncio.AbstractEventLoop | None = None


def rodar(corrotina):
    """Executa uma corrotina. Os passos do pytest-bdd são síncronos.

    ⚠️ **UM loop para a suíte inteira, e isso não é economia: é correção.**

    A versão anterior criava um loop novo a cada chamada. Isso funcionou
    enquanto todos os engines eram nossos — `criar_engine` usa `NullPool`, então
    nenhuma conexão sobrevive entre chamadas e não há o que vazar de um loop
    para outro (ver ADR-0014).

    O `DatabaseSessionService` do ADK quebrou essa premissa: ele constrói o
    **engine dele**, com o pool dele, que não controlamos. A conexão fica presa
    ao loop que a abriu, e o segundo passo de um cenário morre com
    `got Future attached to a different loop` — o mesmo erro que derrubou 29
    cenários na migração para Postgres, de novo, por outra porta.

    Um loop persistente resolve de uma vez e não guarda estado de teste: o que
    isola um caso do outro é o schema do Postgres, não o loop.
    """
    global _loop_da_suite
    if _loop_da_suite is None or _loop_da_suite.is_closed():
        _loop_da_suite = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop_da_suite)
    return _loop_da_suite.run_until_complete(corrotina)


# --------------------------------------------------------------------- fixtures


@pytest.fixture
def url_banco() -> str:
    """URL do Postgres da suíte. Vem da configuração, como a aplicação."""
    return obter_configuracao().url_banco


@pytest.fixture
def schema_teste(url_banco, request):
    """Um schema do Postgres por teste, apagado no fim.

    **É este o isolamento que o plano 1.4 nomeia como risco do P2.** Com
    SQLite, cada teste tinha um arquivo temporário e o isolamento era de
    graça. Com um banco único e compartilhado, dois casos que gravem a mesma
    `(area, data)` colidem no índice parcial do I-01 — e a suíte fica
    intermitente, que é pior que vermelha.

    Schema por teste, e não transação revertida, porque a aplicação abre
    conexões próprias (`criar_app` monta o seu engine) e um `ROLLBACK` no fim
    de uma transação de fora não alcançaria o que elas gravaram.
    """
    nome = f"teste_{uuid4().hex[:12]}"
    yield nome
    # Mesmo que o teste falhe: schema que fica para trás vira lixo acumulado
    # no volume, e eventualmente um `CREATE SCHEMA` lento.
    remover_schema(url_banco, nome)


@pytest.fixture
def banco(url_banco, schema_teste):
    """Engine apontando para o schema deste teste, com o DDL já aplicado."""
    aplicar_schema(url_banco, schema=schema_teste)
    return criar_engine(url_banco, schema=schema_teste)


@pytest.fixture(scope="session")
def schema_regulamento():
    """Um schema com os 96 artigos vetorizados DE VERDADE, uma vez por sessão.

    **Escopo de sessão de propósito, e isso é exceção neste arquivo.** Os
    cenários `@recuperacao` precisam dos vetores reais — o cliente falso de
    `tests/embedding_de_teste.py` gera vetores por hash, e hash não tem
    semântica: a pergunta da piscina não ficaria perto do artigo da piscina.

    Com escopo de função, cada um dos 11 casos `@recuperacao` geraria os 96
    vetores outra vez. São 11 requisições onde uma basta, contra uma quota
    diária de 1.000 — desperdício sem ganho, porque **nenhum destes cenários
    escreve** no regulamento. Dado somente-lido pode ser compartilhado.

    O schema é próprio, e não o `public`, para a suíte não depender de alguém
    ter rodado `aurora-restaurar` antes nem sujar o banco de trabalho.
    """
    from app.infra.embeddings import EmbeddingGemini

    url = obter_configuracao().url_banco
    nome = f"regulamento_{uuid4().hex[:12]}"
    aplicar_schema(url, schema=nome)

    engine = criar_engine(url, schema=nome)
    try:
        # Falha alto se a chave faltar. Não é `skip`: cenário pulado é
        # invisível, e invisível é perdido (regra 3 do CLAUDE.md).
        cliente = EmbeddingGemini()
        quantos = rodar(semear_regulamento(engine, DADOS / "regulamento.md", cliente))
        assert quantos == 96, f"esperava 96 artigos vetorizados, saíram {quantos}"
        yield nome
    finally:
        rodar(engine.dispose())
        remover_schema(url, nome)


@pytest.fixture
def repo(banco):
    return RepositorioPostgres(banco)


@pytest.fixture
def contexto() -> dict:
    """Carrega o que os passos precisam passar entre si."""
    return {}


# ------------------------------------------------------------------ Dado (setup)


@given("o condomínio com os dados iniciais carregados")
def _condominio_semeado(banco):
    rodar(semear(banco, DADOS))


@given("um banco vazio")
def _banco_vazio(banco):
    return banco


# Os passos `Dado` abaixo descrevem uma PRÉ-CONDIÇÃO, não uma ação: eles
# garantem que o mundo está num estado, sem supor que o estado ainda não
# existe. Isso importa porque o seed de `dados/` já traz parte dele — a
# RSV-1377 do 101 e a RSV-4821 do 302 vêm prontas. Recriar cegamente colide
# com o índice e faz o teste falhar por motivo que não é o do cenário.


@given(parsers.parse("que o {apartamento} tem o salão reservado em {data}"))
@given(parsers.parse("que o {apartamento} tinha o salão reservado em {data}"))
def _reserva_salao(banco, repo, contexto, apartamento, data):
    contexto["reserva"] = _garantir_reserva(
        banco, repo, apartamento, "salao-de-festas", data
    )


@given(parsers.parse("que o {apartamento} tem a quadra reservada em {data}"))
@given(parsers.parse("que o {apartamento} tinha a quadra reservada em {data}"))
def _reserva_quadra(banco, repo, contexto, apartamento, data):
    contexto["reserva"] = _garantir_reserva(banco, repo, apartamento, "quadra", data)


@given(parsers.parse("que o {apartamento} tem a reserva {codigo} da quadra em {data}"))
def _reserva_com_codigo(banco, repo, contexto, apartamento, codigo, data):
    reserva = _garantir_reserva(banco, repo, apartamento, "quadra", data, codigo=codigo)
    assert reserva.codigo == codigo, (
        f"o cenário cita {codigo}, mas a reserva existente é {reserva.codigo}"
    )
    contexto["codigo"] = codigo
    contexto["reserva"] = reserva


@given(parsers.parse("que a reserva {codigo} pertence ao {apartamento}"))
def _reserva_de_outro(banco, repo, contexto, codigo, apartamento):
    reserva = _garantir_reserva(
        banco, repo, apartamento, "salao-de-festas", "2030-03-16", codigo=codigo
    )
    assert reserva.apartamento == apartamento
    contexto["codigo"] = codigo


@given("que essa reserva foi cancelada")
def _cancelar_a_reserva(repo, contexto):
    reserva = contexto["reserva"]
    rodar(repo.cancelar_reserva_por_codigo(reserva.apartamento, reserva.codigo))
    contexto["codigo_cancelado"] = reserva.codigo


@given(parsers.parse("que existiu uma reserva de código C, depois cancelada"))
def _reserva_cancelada_qualquer(repo, contexto):
    reserva = rodar(repo.criar_reserva("101", "churrasqueira", date(2030, 8, 1)))
    rodar(repo.cancelar_reserva_por_codigo("101", reserva.codigo))
    contexto["codigo_cancelado"] = reserva.codigo


@given(parsers.parse("uma sessão do {apartamento}"))
def _sessao(contexto, apartamento):
    contexto["apartamento"] = apartamento


@given(parsers.parse("que o {apartamento} não tem reserva da churrasqueira em {data}"))
def _sem_reserva(contexto, apartamento, data):
    contexto["apartamento"] = apartamento


@given(parsers.parse("que o {apartamento} já autorizou a entrada de {nome} em {data}"))
def _autorizacao_existente(repo, contexto, apartamento, nome, data):
    rodar(repo.autorizar_visitante(apartamento, nome, date.fromisoformat(data)))
    contexto["apartamento"] = apartamento


# ----------------------------------------------------------------------- Quando


@when(parsers.parse("o {apartamento} tenta reservar o salão em {data}"))
@when(parsers.parse("o {apartamento} reserva o salão em {data}"))
def _tenta_reservar_salao(repo, contexto, apartamento, data):
    _executar(
        contexto, lambda: repo.criar_reserva(apartamento, "salao-de-festas", date.fromisoformat(data))
    )


@when(parsers.parse("o morador do {apartamento} pede a quadra em {data} de novo"))
def _reserva_quadra_de_novo(repo, contexto, apartamento, data):
    _executar(contexto, lambda: repo.criar_reserva(apartamento, "quadra", date.fromisoformat(data)))


@when(parsers.parse("o {apartamento} cancela essa reserva"))
def _cancela(repo, contexto, apartamento):
    reserva = contexto["reserva"]
    _executar(contexto, lambda: repo.cancelar_reserva_por_codigo(apartamento, reserva.codigo))


@when("qualquer reserva nova é criada")
def _cria_qualquer(repo, contexto):
    nova = rodar(repo.criar_reserva("102", "churrasqueira", date(2030, 9, 9)))
    contexto["nova"] = nova


@when("o morador lista as próprias reservas")
def _lista(repo, contexto):
    contexto["lista"] = rodar(repo.listar_reservas_do_apartamento("101"))


@when(parsers.parse("o morador pede para cancelar a reserva {codigo}"))
def _cancela_por_codigo(repo, contexto, codigo):
    apartamento = contexto.get("apartamento", "101")
    _executar(contexto, lambda: repo.cancelar_reserva_por_codigo(apartamento, codigo))


@when(parsers.parse("o morador pede para cancelar a churrasqueira em {data}"))
def _cancela_inexistente(repo, contexto, data):
    apartamento = contexto.get("apartamento", "101")
    _executar(
        contexto,
        lambda: repo.cancelar_reserva_por_area_data(
            apartamento, "churrasqueira", date.fromisoformat(data)
        ),
    )


@when(parsers.parse("o morador autoriza {nome} em {data} outra vez"))
@when(parsers.parse("o morador tenta autorizar {nome} em {data} de novo"))
def _autoriza_de_novo(repo, contexto, nome, data):
    apartamento = contexto.get("apartamento", "101")
    _executar(
        contexto, lambda: repo.autorizar_visitante(apartamento, nome, date.fromisoformat(data))
    )


@when("o seed é executado")
def _executa_seed(banco):
    rodar(semear(banco, DADOS))


# ------------------------------------------- cenários @api (ADR-0006, P1/P2)


@given("um banco sem o schema aplicado")
def _sem_banco(url_banco, schema_teste, contexto):
    # O schema deste teste ainda não existe: a fixture `banco`, que o cria,
    # não é pedida por este cenário de propósito — quem tem que criá-lo é
    # `criar_app` (ADR-0006).
    assert not _schema_existe(url_banco, schema_teste)
    contexto["url_banco"] = url_banco
    contexto["schema"] = schema_teste


@given("a aplicação ligada ao banco")
def _app_com_banco(url_banco, schema_teste, contexto):
    from fastapi.testclient import TestClient

    from app.api.aplicacao import criar_app

    contexto["url_banco"] = url_banco
    contexto["schema"] = schema_teste
    app = criar_app(url_banco=url_banco, schema=schema_teste)
    rodar(semear(criar_engine(url_banco, schema=schema_teste), DADOS))
    contexto["app"] = app
    contexto["cliente"] = TestClient(app)


@given("que uma reserva foi criada pela aplicação")
def _reserva_pela_app(contexto):
    repositorio = contexto["app"].state.repositorio
    reserva = rodar(repositorio.criar_reserva("101", "churrasqueira", date(2030, 6, 15)))
    contexto["reserva"] = reserva


@when("a aplicação é construída")
def _constroi_app(url_banco, schema_teste, contexto):
    from fastapi.testclient import TestClient

    from app.api.aplicacao import criar_app

    # Uma URL forçada pelo `Dado` vence a da configuração: é como o cenário do
    # banco fora do ar aponta para um endereço onde não há ninguém.
    url = contexto.get("url_banco_forcada", url_banco)
    contexto.setdefault("url_banco", url)
    contexto.setdefault("schema", schema_teste)

    # A falha é capturada em vez de propagar porque DOIS cenários usam este
    # passo, e num deles falhar é o comportamento esperado (ADR-0014, o erro
    # legível). Quem precisa de sucesso confere via `_banco_existe`, que
    # mostra o erro guardado se houver.
    try:
        app = criar_app(url_banco=url, schema=schema_teste)
    except Exception as exc:  # noqa: BLE001 — o `Então` decide se era esperada
        contexto["erro_subida"] = exc
        return

    contexto["erro_subida"] = None
    contexto["app"] = app
    contexto["cliente"] = TestClient(app)


@when("a aplicação é construída de novo sobre o mesmo banco")
def _reconstroi_app(contexto):
    from fastapi.testclient import TestClient

    from app.api.aplicacao import criar_app

    # Equivale ao reinício do processo: instância nova, mesmo schema.
    app = criar_app(url_banco=contexto["url_banco"], schema=contexto["schema"])
    contexto["app"] = app
    contexto["cliente"] = TestClient(app)


@when("uma reserva é gravada diretamente no banco")
def _grava_direto(contexto):
    from sqlalchemy import text

    engine = criar_engine(contexto["url_banco"], schema=contexto["schema"])

    async def inserir():
        try:
            async with engine.begin() as c:
                await c.execute(
                    text(
                        "INSERT INTO reserva (codigo, apartamento, area, data, ativa) "
                        "VALUES ('RSV-7777', '101', 'churrasqueira', '2030-06-20', 1)"
                    )
                )
        finally:
            await engine.dispose()

    rodar(inserir())
    contexto["codigo"] = "RSV-7777"


@then("o schema passa a existir")
def _banco_existe(contexto):
    erro = contexto.get("erro_subida")
    assert erro is None, f"a subida falhou antes de criar o schema: {erro!r}"
    assert _schema_existe(contexto["url_banco"], contexto["schema"]), (
        "criar_app não criou o schema — ADR-0006 diz que quem o cria é a aplicação"
    )


@then("as rotas de verificação respondem sem erro")
def _rotas_ok(contexto):
    resposta = contexto["cliente"].get("/apartamentos/101/reservas")
    assert resposta.status_code == 200, resposta.text


@then("ela aparece em GET /apartamentos/{numero}/reservas")
def _aparece_na_rota(contexto):
    resposta = contexto["cliente"].get("/apartamentos/101/reservas")
    assert resposta.status_code == 200, resposta.text
    assert contexto["codigo"] in {r["codigo"] for r in resposta.json()}


@then("a reserva continua aparecendo nas reservas do apartamento")
@then("a reserva continua lá")
def _reserva_sobreviveu(contexto):
    reserva = contexto["reserva"]
    resposta = contexto["cliente"].get(f"/apartamentos/{reserva.apartamento}/reservas")
    assert resposta.status_code == 200, resposta.text
    assert reserva.codigo in {r["codigo"] for r in resposta.json()}


# ------------------------------------------------- restauração (P2, ADR-0002)


@given("que uma reserva foi criada e outra cancelada")
def _mexe_antes_de_restaurar(repo, contexto):
    nova = rodar(repo.criar_reserva("102", "churrasqueira", date(2030, 11, 11)))
    rodar(repo.cancelar_reserva_por_codigo("101", "RSV-1377"))
    contexto["codigo_novo"] = nova.codigo


@pytest.fixture
def cliente_embedding(contexto):
    """Cliente de embedding falso, compartilhado pelos passos do cenário."""
    from tests.embedding_de_teste import EmbeddingDeTeste

    cliente = EmbeddingDeTeste()
    contexto["cliente_embedding"] = cliente
    return cliente


@when("a restauração é executada")
def _restaura(banco, url_banco, schema_teste, contexto, cliente_embedding):
    # Exercita o mesmo caminho do comando `aurora-restaurar`: aplicar schema
    # (idempotente), semear o domínio e indexar o regulamento. O comando em si
    # só acrescenta a leitura da configuração e o cliente real de embedding.
    aplicar_schema(url_banco, schema=schema_teste)
    rodar(semear(banco, DADOS))
    # O cliente é falso de propósito: estes cenários são `@storage`, e
    # `@storage` significa que rodam sem chave de API. Ver
    # `tests/embedding_de_teste.py`.
    contexto["trechos_gravados"] = rodar(
        semear_regulamento(banco, DADOS / "regulamento.md", cliente_embedding)
    )


@then(parsers.parse("o apartamento {apartamento} tem a reserva {codigo} da quadra em {data}"))
def _tem_reserva_inicial(repo, apartamento, codigo, data):
    reservas = rodar(repo.listar_reservas_do_apartamento(apartamento))
    achadas = [r for r in reservas if r.codigo == codigo and r.data.isoformat() == data]
    assert achadas, f"{codigo} não voltou para o apartamento {apartamento}"


@then(parsers.parse("o apartamento {apartamento} tem {nome} autorizada em {data}"))
def _tem_visitante_inicial(repo, apartamento, nome, data):
    visitantes = rodar(repo.listar_visitantes_do_apartamento(apartamento))
    assert [v for v in visitantes if v.nome == nome and v.data.isoformat() == data], (
        f"{nome} não voltou para o apartamento {apartamento}"
    )


@then("a reserva criada depois do estado inicial não existe mais")
def _reserva_nova_sumiu(repo, contexto):
    reservas = rodar(repo.listar_reservas_do_apartamento("102"))
    assert contexto["codigo_novo"] not in {r.codigo for r in reservas}


@when("reservas são criadas e canceladas")
def _mexe_em_reservas(repo):
    reserva = rodar(repo.criar_reserva("102", "quadra", date(2030, 10, 10)))
    rodar(repo.cancelar_reserva_por_codigo("102", reserva.codigo))


@when("visitantes são autorizados")
def _autoriza(repo):
    rodar(repo.autorizar_visitante("102", "Teste da Silva", date(2030, 10, 10)))


@when(parsers.parse('se tenta gravar uma reserva da área "{area}"'))
def _grava_area_invalida(banco, contexto, area):
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    async def inserir():
        async with banco.begin() as c:
            await c.execute(
                text(
                    "INSERT INTO reserva (codigo, apartamento, area, data, ativa) "
                    "VALUES ('RSV-9999', '101', :a, '2030-12-01', 1)"
                ),
                {"a": area},
            )

    try:
        rodar(inserir())
        contexto["erro"] = None
    except IntegrityError as exc:
        contexto["erro"] = exc


# ------------------------------------------------------------------------ Então


@then("a reserva não é criada")
@then("nenhuma reserva nova é criada")
@then("nenhuma autorização nova é criada")
def _recusado(contexto):
    assert contexto["erro"] is not None, "esperava recusa, mas a gravação passou"


@then("a recusa não revela de quem é a reserva existente")
def _sem_vazamento(contexto):
    erro = contexto["erro"]
    assert isinstance(erro, AreaIndisponivel)
    # I-06: a exceção não pode carregar o apartamento dono nem o código.
    assert not hasattr(erro, "apartamento")
    assert "302" not in str(erro)


@then("a resposta informa que ele já tem essa reserva")
def _ja_e_sua(contexto):
    assert isinstance(contexto["erro"], JaReservadaPorVoce)


@then(parsers.parse("o {apartamento} continua com exatamente uma reserva da quadra em {data}"))
def _uma_reserva(repo, apartamento, data):
    reservas = rodar(repo.listar_reservas_do_apartamento(apartamento))
    quadra = [r for r in reservas if r.area == "quadra" and r.data.isoformat() == data]
    assert len(quadra) == 1, f"esperava 1 reserva, achei {len(quadra)}"


@then(parsers.parse("a quadra em {data} deixa de constar nas reservas do {apartamento}"))
@then(parsers.parse("a quadra em {data} não aparece na lista"))
def _quadra_sumiu(repo, data, **_):
    reservas = rodar(repo.listar_reservas_do_apartamento("101"))
    assert not [r for r in reservas if r.area == "quadra" and r.data.isoformat() == data]


@then(parsers.parse("a quadra passa a constar como livre em {data}"))
def _quadra_livre(repo, data):
    assert rodar(repo.data_esta_livre("quadra", date.fromisoformat(data))) is True


@then(parsers.parse("a reserva do {apartamento} é criada"))
def _criada(contexto, apartamento):
    assert contexto["erro"] is None, f"recusado: {contexto['erro']}"
    assert contexto["resultado"].apartamento == apartamento


@then("seu código é diferente de C")
def _codigo_diferente(contexto):
    assert contexto["nova"].codigo != contexto["codigo_cancelado"]


@then("o código dessa reserva não aparece na resposta")
def _codigo_nao_aparece(contexto):
    codigos = {r.codigo for r in contexto["lista"]}
    assert contexto["codigo_cancelado"] not in codigos


@then(parsers.parse("a reserva {codigo} deixa de constar nas reservas do {apartamento}"))
def _reserva_cancelada(repo, codigo, apartamento):
    reservas = rodar(repo.listar_reservas_do_apartamento(apartamento))
    assert codigo not in {r.codigo for r in reservas}


@then("a resposta identifica qual reserva foi cancelada")
def _identifica(contexto):
    resultado = contexto["resultado"]
    assert resultado.area and resultado.data, "o cancelamento precisa devolver área e data"


@then(parsers.parse("nada das reservas do {apartamento} é alterado"))
def _nada_alterado(repo, contexto, apartamento):
    assert isinstance(contexto["erro"], ReservaNaoEncontrada)
    reservas = rodar(repo.listar_reservas_do_apartamento(apartamento))
    assert contexto["codigo"] in {r.codigo for r in reservas}


@then("a resposta não confirma nem nega a existência dessa reserva")
def _resposta_opaca(contexto):
    # ADR-0004: código alheio e código inexistente produzem a MESMA exceção.
    # Distinguir transformaria a ferramenta num oráculo sobre reservas alheias.
    erro = contexto["erro"]
    assert type(erro) is ReservaNaoEncontrada
    assert not hasattr(erro, "apartamento")


@then("nada é alterado")
def _nada(contexto):
    assert isinstance(contexto["erro"], ReservaNaoEncontrada)


@then("a resposta informa que não há essa reserva")
def _informa_inexistente(contexto):
    assert isinstance(contexto["erro"], ReservaNaoEncontrada)


@then("a resposta informa que a pessoa já está autorizada nessa data")
def _ja_autorizado(contexto):
    assert isinstance(contexto["erro"], VisitanteJaAutorizado)


@then(parsers.parse("o {apartamento} tem exatamente uma autorização para {nome} em {data}"))
def _uma_autorizacao(repo, apartamento, nome, data):
    visitantes = rodar(repo.listar_visitantes_do_apartamento(apartamento))
    iguais = [v for v in visitantes if v.nome == nome and v.data.isoformat() == data]
    assert len(iguais) == 1, f"esperava 1 autorização, achei {len(iguais)}"


@then(parsers.parse("existem {quantidade:d} apartamentos"))
def _conta_apartamentos(banco, quantidade):
    assert _contar(banco, "apartamento") == quantidade


@then(parsers.parse("existem {quantidade:d} áreas"))
def _conta_areas(banco, quantidade):
    assert _contar(banco, "area") == quantidade


@then(parsers.parse("a taxa do salão de festas é {taxa:g}"))
def _taxa_salao(repo, taxa):
    assert rodar(repo.buscar_area("salao-de-festas")).taxa == taxa


@then(parsers.parse("a taxa da quadra é {taxa:g}"))
def _taxa_quadra(repo, taxa):
    assert rodar(repo.buscar_area("quadra")).taxa == taxa


@then("os arquivos em dados/ continuam byte-idênticos aos originais")
def _dados_intactos(contexto):
    # O hash é tirado no início da sessão de teste (fixture autouse abaixo).
    assert _hash_dados() == contexto["hash_dados"]


@then("a gravação é recusada pelo banco")
def _recusada_pelo_banco(contexto):
    # Prova que a REFERENCES do DDL está valendo. No SQLite isto dependia do
    # PRAGMA foreign_keys por conexão, e sem ele a linha entrava em silêncio;
    # o Postgres sempre impõe. O cenário continua valendo o que custa: ele
    # pega o dia em que alguém escrever a tabela sem a REFERENCES.
    assert contexto["erro"] is not None, "o banco aceitou área inexistente"


# --------------------------------------------------------------------- apoio


@pytest.fixture(autouse=True)
def _guardar_hash_dados(contexto):
    contexto["hash_dados"] = _hash_dados()


def _schema_existe(url: str, schema: str) -> bool:
    """Pergunta ao catálogo do Postgres se o schema existe."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    async def consultar() -> bool:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as c:
                achado = (
                    await c.execute(
                        text(
                            "SELECT 1 FROM information_schema.schemata "
                            "WHERE schema_name = :s"
                        ),
                        {"s": schema},
                    )
                ).first()
            return achado is not None
        finally:
            await engine.dispose()

    return rodar(consultar())


def _hash_dados() -> str:
    h = hashlib.sha256()
    for caminho in sorted(DADOS.iterdir()):
        h.update(caminho.name.encode())
        h.update(caminho.read_bytes())
    return h.hexdigest()


def _garantir_reserva(engine, repo, apartamento: str, area: str, data: str, *, codigo=None):
    """Deixa o mundo com essa reserva ativa, criando-a só se ainda não houver.

    Se já existir (o seed de `dados/` traz algumas), devolve a existente em vez
    de colidir com o índice único.
    """
    from sqlalchemy import text

    d = date.fromisoformat(data) if isinstance(data, str) else data

    async def existente():
        sql = text(
            "SELECT codigo, apartamento, area, data FROM reserva "
            "WHERE area = :a AND data = :d AND ativa = 1"
        )
        async with engine.connect() as c:
            return (await c.execute(sql, {"a": area, "d": d.isoformat()})).first()

    linha = rodar(existente())
    if linha is not None:
        from app.dominio.modelos import Reserva

        return Reserva(
            codigo=linha[0], apartamento=linha[1], area=linha[2], data=date.fromisoformat(linha[3])
        )

    if codigo is None:
        return rodar(repo.criar_reserva(apartamento, area, d))

    # Código fixado pelo cenário: inserção direta, porque o gerador do
    # repositório sorteia (regra 5). É setup, não caminho de uso.
    async def inserir():
        async with engine.begin() as c:
            await c.execute(
                text(
                    "INSERT INTO reserva (codigo, apartamento, area, data, ativa) "
                    "VALUES (:c, :ap, :a, :d, 1)"
                ),
                {"c": codigo, "ap": apartamento, "a": area, "d": d.isoformat()},
            )

    rodar(inserir())
    from app.dominio.modelos import Reserva

    return Reserva(codigo=codigo, apartamento=apartamento, area=area, data=d)


def _contar(engine, tabela: str) -> int:
    from sqlalchemy import text

    async def contar():
        async with engine.connect() as c:
            return (await c.execute(text(f"SELECT COUNT(*) FROM {tabela}"))).scalar_one()

    return rodar(contar())


def _executar(contexto: dict, acao) -> None:
    """Roda a ação guardando resultado ou recusa, para o `Então` conferir."""
    try:
        contexto["resultado"] = rodar(acao())
        contexto["erro"] = None
    except Exception as exc:  # noqa: BLE001 — o teste decide se era esperada
        contexto["resultado"] = None
        contexto["erro"] = exc


# Passos dos cenários @ferramenta vivem em módulo próprio — este arquivo já
# passou de 400 linhas. O import traz os registros do pytest-bdd junto.
from tests.steps_ferramentas import *  # noqa: E402, F401, F403

# Passos dos cenários que dependem do Postgres (ADR-0014, plano 1.4).
from tests.steps_postgres import *  # noqa: E402, F401, F403

# Passos dos cenários do regulamento vetorizado (ADR-0015/0016/0020).
from tests.steps_regulamento import *  # noqa: E402, F401, F403

# Passos dos cenários @estrutura — inspecionam a árvore de agentes.
from tests.steps_estrutura import *  # noqa: E402, F401, F403

# Passos dos cenários @conversa — o assistente respondendo de verdade.
from tests.steps_conversa import *  # noqa: E402, F401, F403

# Passos da rota de confirmações — a Garantia 1 em ação.
from tests.steps_confirmacao import *  # noqa: E402, F401, F403

# Passos dos cenários de quota — stub HTTP que responde 429.
from tests.steps_quota import *  # noqa: E402, F401, F403
