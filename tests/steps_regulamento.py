"""Passos dos cenários do regulamento vetorizado (P4 do plano 1.4).

Cobrem ADR-0015 (recuperação semântica), ADR-0016 (a unidade é o artigo) e
ADR-0020 (`gemini-embedding-001`, 768 dimensões, `task_type` como parâmetro).

Todos rodam **sem chave de API**: o cliente de embedding é o falso de
`tests/embedding_de_teste.py`. O que estes cenários cobram não é qualidade de
vetor — é que haja um vetor por artigo, com a dimensão que o banco impõe, e
que o `task_type` seja o certo em cada sentido.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, then, when
from sqlalchemy import text

from app.dominio.regulamento import fatiar_em_artigos
from app.infra.embeddings import DIMENSOES
from app.infra.seed import semear_regulamento

RAIZ = Path(__file__).resolve().parent.parent
REGULAMENTO = RAIZ / "dados" / "regulamento.md"


def _consultar(banco, sql: str, parametros: dict | None = None):
    """Roda um SELECT e devolve as linhas."""
    from tests.conftest import rodar

    async def executar():
        async with banco.connect() as c:
            return (await c.execute(text(sql), parametros or {})).all()

    return rodar(executar())


# ------------------------------------------------- a dimensão é do banco


@given("o schema do banco aplicado")
def _schema_aplicado(banco, contexto):
    contexto["banco"] = banco


@then(parsers.parse(
    "a coluna de embedding da tabela de trechos do regulamento tem {esperado:d} dimensões"
))
def _dimensao_da_coluna(banco, esperado):
    # `atttypmod` do Postgres guarda a dimensão declarada em `vector(N)`.
    linhas = _consultar(
        banco,
        "SELECT a.atttypmod FROM pg_attribute a "
        "JOIN pg_class c ON c.oid = a.attrelid "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE c.relname = 'regulamento_trecho' AND a.attname = 'embedding' "
        "AND n.nspname = current_schema()",
    )
    assert linhas, "a tabela regulamento_trecho não tem coluna `embedding`"
    assert linhas[0][0] == esperado, (
        f"a coluna é vector({linhas[0][0]}), esperava vector({esperado}). "
        "Acima de 2.000 o pgvector não aceita índice hnsw nem ivfflat (M-6)."
    )
    assert esperado == DIMENSOES, (
        f"o cenário diz {esperado} e o código diz {DIMENSOES} — schema e "
        "chamada ao modelo PRECISAM concordar, senão toda gravação é recusada."
    )


@then("gravar um vetor de dimensão diferente é recusado pelo banco")
def _dimensao_errada_recusada(banco):
    from tests.conftest import rodar

    # 3 dimensões num vector(768). Isto é o que torna a `M-6` imposta por
    # CÓDIGO e não por disciplina: não há como gravar o tamanho errado.
    async def inserir():
        async with banco.begin() as c:
            await c.execute(
                text(
                    "INSERT INTO regulamento_trecho (titulo, capitulo, texto, embedding) "
                    "VALUES ('Art. 0', 'Cap. teste', 'texto', CAST('[1,2,3]' AS vector))"
                )
            )

    try:
        rodar(inserir())
    except Exception:
        return
    raise AssertionError(
        "o banco aceitou um vetor de 3 dimensões numa coluna vector(768). "
        "A dimensão deixou de ser imposta pelo schema."
    )


# --------------------------------------------- um vetor por artigo


@given("o regulamento de dados/regulamento.md")
def _regulamento_de_origem(contexto):
    assert REGULAMENTO.exists(), f"{REGULAMENTO} não existe"
    contexto["artigos_esperados"] = fatiar_em_artigos(
        REGULAMENTO.read_text(encoding="utf-8")
    )
    assert contexto["artigos_esperados"], "o fatiador não achou artigo nenhum"


@then("existe um trecho gravado para cada artigo do regulamento")
def _um_trecho_por_artigo(banco, contexto):
    esperados = {t.titulo for t in contexto["artigos_esperados"]}
    gravados = {l[0] for l in _consultar(banco, "SELECT titulo FROM regulamento_trecho")}

    faltando = esperados - gravados
    sobrando = gravados - esperados
    assert not faltando, f"{len(faltando)} artigos não foram gravados: {sorted(faltando)[:5]}"
    assert not sobrando, f"gravados artigos que não existem no documento: {sorted(sobrando)[:5]}"
    assert len(gravados) == len(esperados), (
        f"{len(gravados)} trechos para {len(esperados)} artigos"
    )


@then(parsers.parse(
    "cada trecho gravado tem o seu próprio vetor, com {esperado:d} dimensões"
))
def _cada_trecho_tem_vetor(banco, esperado):
    linhas = _consultar(
        banco,
        "SELECT titulo, vector_dims(embedding) FROM regulamento_trecho",
    )
    assert linhas, "nenhum trecho gravado"
    erradas = [(t, d) for t, d in linhas if d != esperado]
    assert not erradas, f"trechos com dimensão diferente de {esperado}: {erradas[:5]}"


@then("nenhum vetor gravado é idêntico ao de outro trecho")
def _vetores_distintos(banco):
    # ⚠️ A armadilha `M-5` em forma de teste. Com `gemini-embedding-2`, passar
    # os artigos como lista de strings devolve UM vetor agregado — a média
    # semântica do regulamento inteiro — sem erro nenhum, e a busca passa a
    # responder sempre a mesma coisa. O ADR-0020 escolheu o `-001`, que não tem
    # essa armadilha; esta asserção fica para o dia em que alguém migrar.
    linhas = _consultar(
        banco,
        "SELECT count(*) AS total, count(DISTINCT embedding) AS distintos "
        "FROM regulamento_trecho",
    )
    total, distintos = linhas[0]
    assert total == distintos, (
        f"{total} trechos gravados, mas só {distintos} vetores distintos. "
        "Vetores repetidos significam agregação: a busca responderia sempre a "
        "mesma coisa, sem nunca dar erro."
    )


# ------------------------------------- a assimetria do task_type (ADR-0020)


@given("um cliente de embedding que registra o task_type de cada chamada")
def _cliente_que_registra(cliente_embedding, contexto):
    contexto["cliente_embedding"] = cliente_embedding


@when("a restauração gera os vetores do regulamento")
def _gera_vetores(banco, contexto):
    from tests.conftest import rodar

    contexto["trechos_gravados"] = rodar(
        semear_regulamento(banco, REGULAMENTO, contexto["cliente_embedding"])
    )


@when("uma pergunta do morador é convertida em vetor para a busca")
def _converte_pergunta(contexto):
    from tests.conftest import rodar

    contexto["vetor_da_pergunta"] = rodar(
        contexto["cliente_embedding"].gerar_de_consulta(
            "até que horas a piscina funciona aos domingos?"
        )
    )


@then(parsers.parse(
    'a chamada que gerou os vetores dos artigos usou task_type "{tarefa}"'
))
def _tarefa_dos_documentos(contexto, tarefa):
    chamadas = contexto["cliente_embedding"].chamadas
    # A chamada dos documentos é a que recebeu MAIS DE UM texto: são os 96
    # artigos num `:batchEmbedContents` só (spike 2.4, achado 9).
    muitas = [t for t, quantidade in chamadas if quantidade > 1]
    assert muitas, f"nenhuma chamada com vários textos. Chamadas: {chamadas}"
    assert all(t == tarefa for t in muitas), (
        f"os artigos foram vetorizados com {muitas}, esperava {tarefa!r}. "
        "A assimetria da busca é o argumento que decidiu o ADR-0020."
    )


@then(parsers.parse(
    'a chamada que converteu a pergunta usou task_type "{tarefa}"'
))
def _tarefa_da_consulta(contexto, tarefa):
    chamadas = contexto["cliente_embedding"].chamadas
    assert chamadas[-1][0] == tarefa, (
        f"a pergunta foi convertida com {chamadas[-1][0]!r}, esperava {tarefa!r}. "
        "Usar RETRIEVAL_DOCUMENT na pergunta desfaz a assimetria em silêncio: "
        "a busca continua respondendo, só pior."
    )


# ------------------------------- a chave do .env chega ao cliente (regressão)


@given("um arquivo de ambiente com a chave do Gemini preenchida")
def _env_com_chave(contexto, tmp_path):
    arquivo = tmp_path / ".env"
    # Uma chave de mentira: o cenário prova o CAMINHO da configuração até o
    # cliente, não que a chave seja aceita pelo Google. Nenhuma chamada de
    # rede acontece ao construir o cliente.
    arquivo.write_text("GOOGLE_API_KEY=chave-de-teste-nao-funcional\n", encoding="utf-8")
    contexto["arquivo_env"] = arquivo


@when("a configuração é lida desse arquivo")
def _le_configuracao(contexto):
    from app.config import Configuracao

    # Instanciada direto, sem o `lru_cache` de `obter_configuracao`, para o
    # cenário não depender nem alterar a configuração do processo.
    contexto["configuracao"] = Configuracao(_env_file=contexto["arquivo_env"])


@then("a chave chega à configuração")
def _chave_na_configuracao(contexto):
    chave = contexto["configuracao"].google_api_key
    assert chave == "chave-de-teste-nao-funcional", (
        f"a configuração não leu a chave do arquivo (veio {chave!r}). "
        "Era exatamente este o bug: o .env tinha a chave e nada a lia."
    )


@then("o cliente de embedding é construído com ela, sem recusar por falta de chave")
def _cliente_construido(contexto):
    from app.infra.embeddings import ChaveDeApiAusente, EmbeddingGemini

    try:
        EmbeddingGemini(chave=contexto["configuracao"].google_api_key)
    except ChaveDeApiAusente as erro:
        raise AssertionError(
            "o cliente recusou por falta de chave, com a chave em mãos. "
            f"É o bug de volta: {erro}"
        ) from None


# ═══════════════════════════════════════════════════════════════════════════
# P1 do plano 4 — os cenários @recuperacao, contra os vetores REAIS
#
# Eles vão pela FERRAMENTA, não pelo recuperador direto, porque metade do que
# cobram é a projeção do retorno: no máximo 3 artigos, cada um com o seu
# capítulo, nunca o capítulo inteiro. É a Garantia 4 em forma de retorno, e ela
# vive na ferramenta.
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def busca(schema_regulamento, url_banco):
    """A ferramenta `buscar_no_regulamento`, ligada aos vetores reais."""
    from app.agentes.ferramentas.regulamento import criar_ferramentas_de_regulamento
    from app.infra.banco import criar_engine
    from app.infra.embeddings import EmbeddingGemini
    from app.infra.recuperacao import RecuperadorDeRegulamento

    engine = criar_engine(url_banco, schema=schema_regulamento)
    recuperador = RecuperadorDeRegulamento(engine, EmbeddingGemini())
    ferramenta = criar_ferramentas_de_regulamento(recuperador)[0]
    yield ferramenta.func
    from tests.conftest import rodar

    rodar(engine.dispose())


@when(parsers.parse('busco no regulamento por "{assunto}"'))
def _busco(busca, contexto, assunto):
    from tests.conftest import rodar

    # A ferramenta não usa o `tool_context` — consultar texto não depende do
    # apartamento da sessão. Passar `None` deixa isso explícito.
    contexto["retorno"] = rodar(busca(assunto=assunto, tool_context=None))
    contexto["artigos"] = contexto["retorno"]["artigos"]


def _textos(contexto) -> str:
    return "\n".join(a["texto"] for a in contexto["artigos"])


def _titulos(contexto) -> list[str]:
    return [a["artigo"] for a in contexto["artigos"]]


@then("o trecho devolvido contém o horário de fechamento aos domingos")
def _horario_domingo(contexto):
    # Art. 22, II: "Aos domingos e feriados, a piscina funciona das 9h às 20h."
    # A asserção é sobre o NÚMERO, não sobre a frase: o texto do artigo é o do
    # documento e não muda, mas comparar a frase inteira quebraria se o
    # fatiador mudasse um espaço.
    assert "20h" in _textos(contexto), (
        f"o horário de fechamento não veio. Artigos: {_titulos(contexto)}"
    )


def _romano(texto: str) -> str:
    """Extrai o numeral do capítulo: `Capítulo VIII: Animais` -> `VIII`.

    ⚠️ Comparar capítulo por PREFIXO de string é bug, e ele passou por aqui:
    `"Capítulo VIII".startswith("Capítulo VI")` é **True**, porque "VIII"
    começa com "VI". O cenário do cachorro-na-quadra ficou vermelho por isso,
    com a recuperação certa. Numeral romano se compara inteiro.
    """
    import re

    achado = re.search(r"Cap[íi]tulo\s+([IVXLC]+)", texto)
    assert achado, f"não consegui ler o numeral do capítulo em {texto!r}"
    return achado.group(1)


@then(parsers.parse("o trecho devolvido vem do {capitulo}"))
def _vem_do_capitulo(contexto, capitulo):
    # O cenário escreve "Capítulo VIII — Animais" e o documento diz
    # "Capítulo VIII: Animais de estimação". Casar pelo ROMANO, que é a parte
    # estável: o título do capítulo é redação do documento, não contrato.
    esperado = _romano(capitulo)
    capitulos = [a["capitulo"] for a in contexto["artigos"]]
    assert capitulos, "nenhum artigo devolvido para a pergunta"
    assert _romano(capitulos[0]) == esperado, (
        f"o primeiro artigo veio do Capítulo {_romano(capitulos[0])}, esperava "
        f"{esperado}. Todos: {list(zip(_titulos(contexto), capitulos))}"
    )


@then(parsers.parse("a lista devolvida contém o {artigo}"))
def _lista_contem(contexto, artigo):
    assert artigo in _titulos(contexto), (
        f"{artigo} não veio na lista. Veio: {_titulos(contexto)}"
    )


@then("a lista devolvida não contém o capítulo inteiro de nenhum dos dois")
def _nao_traz_capitulo_inteiro(contexto):
    # O recorte é por ARTIGO (ADR-0016). Cada texto devolvido tem que ser
    # muito menor que o capítulo de onde ele saiu — senão o que voltou foi o
    # capítulo, e a Garantia 4 cai.
    bruto = REGULAMENTO.read_text(encoding="utf-8")
    todos = fatiar_em_artigos(bruto)
    for devolvido in contexto["artigos"]:
        do_capitulo = [t for t in todos if t.capitulo == devolvido["capitulo"]]
        tamanho_do_capitulo = sum(len(t.texto) for t in do_capitulo)
        assert len(devolvido["texto"]) < tamanho_do_capitulo * 0.6, (
            f"{devolvido['artigo']} devolveu {len(devolvido['texto'])} chars de um "
            f"capítulo de {tamanho_do_capitulo} — parece o capítulo, não o artigo"
        )


@then(parsers.parse("o {artigo} trata de animais em áreas comuns"))
def _trata_de_animais(contexto, artigo):
    achados = [a for a in contexto["artigos"] if a["artigo"] == artigo]
    assert achados, f"{artigo} não veio na lista: {_titulos(contexto)}"
    texto = achados[0]["texto"].lower()
    assert "animais" in texto or "animal" in texto, (
        f"{artigo} veio, mas não fala de animais: {texto[:120]!r}"
    )


@then(parsers.parse("nenhum trecho do {capitulo} é devolvido como resposta principal"))
def _nao_e_resposta_principal(contexto, capitulo):
    esperado = _romano(capitulo)
    capitulos = [a["capitulo"] for a in contexto["artigos"]]
    assert capitulos, "nenhum artigo devolvido"
    # "resposta principal" = o primeiro, o mais próximo. O capítulo pode
    # aparecer mais embaixo na lista sem estragar a resposta.
    assert _romano(capitulos[0]) != esperado, (
        f"o primeiro artigo veio do Capítulo {esperado}, que é o capítulo que a "
        "pergunta menciona e não é onde a resposta mora"
    )


@then("nenhum trecho é devolvido")
def _nada_devolvido(contexto):
    assert contexto["artigos"] == [], (
        "a busca devolveu artigo para uma pergunta fora do escopo: "
        f"{_titulos(contexto)}. É o modo de falha que o corte de 0,65 existe "
        "para impedir — 'achei errado' chega ao morador como resposta."
    )


@then("a resposta informa que o assunto não está no regulamento")
def _informa_que_nao_tem(contexto):
    aviso = contexto["retorno"].get("aviso", "")
    assert aviso, (
        "lista vazia sem aviso nenhum deixa o modelo adivinhar se a busca "
        "falhou ou se não há regra sobre o assunto"
    )
    assert "regulamento" in aviso.lower()


@then("o trecho devolvido é menor que um quinto do documento")
def _menor_que_um_quinto(contexto):
    documento = len(REGULAMENTO.read_text(encoding="utf-8"))
    devolvido = len(_textos(contexto))
    limite = documento / 5
    assert devolvido < limite, (
        f"devolveu {devolvido} chars de um documento de {documento} "
        f"(limite {limite:.0f}). O teto de 3 artigos do ADR-0021 existe para isso."
    )


@then(parsers.parse('o trecho devolvido não contém "{proibido}"'))
@then(parsers.parse('não contém "{proibido}"'))
def _nao_contem(contexto, proibido):
    # Os três marcadores são únicos no documento e exclusivos de capítulos que
    # tratam de OUTROS assuntos. Asserção por palavra genérica daria falso
    # positivo: o próprio Cap. IV fala de "animais de qualquer espécie".
    assert proibido not in _textos(contexto), (
        f"{proibido!r} apareceu na resposta — veio trecho de um capítulo que "
        f"trata de outro assunto. Artigos: {_titulos(contexto)}"
    )
