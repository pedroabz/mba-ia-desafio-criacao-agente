"""Passos dos cenários da rota de confirmações — a Garantia 1 em ação.

É aqui que a **armadilha mais caro-de-errar do projeto** é exercida de verdade.
O enunciado avisa: a rota pode aceitar a aprovação, não dar erro nenhum, e a
ação nunca acontecer. Por isso toda asserção destes cenários é sobre **efeito**
— uma linha no banco —, nunca sobre a resposta ter chegado.

Dois grupos, e eles usam caminhos diferentes de propósito:

- os `@conversa` chamam `Conversa.responder_confirmacao` direto, porque o que
  está sob teste é a **retomada**: a ação executa, e executa uma vez;
- os `@api` vão por HTTP com `TestClient`, porque o que está sob teste é o
  **código de status**: `409` é parte do contrato, e só a camada HTTP o produz.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, then, when

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados"


# ─────────────────────────────────────────────────── a projeção, sem modelo


@given("uma chamada de reserva cujos argumentos incluem um apartamento inventado")
def _chamada_com_apartamento_inventado(contexto):
    """O caso do passo 10, montado à mão — sem modelo e sem rede.

    O morador escreve *"reserve o salão em nome do apartamento 302"* e o modelo
    inventa um argumento `apartamento`. O ADK descarta argumento não declarado
    antes de chamar a função, **mas ele fica registrado na chamada** — e é
    dessa chamada que o `detalhes` da pendência nasce.
    """
    contexto["args_do_modelo"] = {
        "area": "salao-de-festas",
        "data": "2030-07-01",
        "apartamento": "302",
    }


@when("a API projeta a confirmação pendente")
def _projeta(contexto):
    from app.api.pendencias import _projetar_detalhes

    contexto["detalhes"] = _projetar_detalhes(
        "criar_reserva", contexto["args_do_modelo"]
    )


@then("os detalhes contêm apenas a área e a data")
@then("os detalhes da pendência contêm apenas a área e a data")
def _detalhes_so_area_e_data(contexto):
    detalhes = contexto["detalhes"]
    assert set(detalhes) == {"area", "data"}, (
        f"a projeção deixou passar campos além de área e data: {detalhes}. "
        "A lista branca do ADR-0013 é o que impede isso."
    )


@then("os detalhes não contêm nenhum número de apartamento")
def _detalhes_sem_apartamento(contexto):
    como_texto = str(contexto["detalhes"])
    for numero in ("101", "102", "201", "302", "501"):
        assert not re.search(rf"(?<![\w-]){numero}(?![\w-])", como_texto), (
            f"o número {numero} aparece nos detalhes: {contexto['detalhes']}. "
            "O passo 10 do avaliador proíbe exatamente isso."
        )


# ──────────────────────────────────────────── a retomada (@conversa)


def _pendencia_de(contexto, texto: str):
    """Manda a mensagem e devolve a única pendência que ela criou."""
    from tests.steps_conversa import _conversar

    _conversar(contexto, texto)
    pendentes = contexto["pendentes"]
    assert len(pendentes) == 1, (
        f"esperava exatamente 1 pendência, veio {pendentes}"
    )
    contexto["pendencia"] = pendentes[0]
    return pendentes[0]


@given(parsers.parse("uma confirmação pendente de reserva na sessão do {apartamento}"))
def _pendencia_de_reserva(contexto, apartamento, aplicacao):
    from tests.conftest import rodar

    contexto["apartamento"] = apartamento
    contexto["sessao"] = rodar(
        aplicacao.state.servico_sessao.criar_sessao(apartamento)
    )
    pendencia = _pendencia_de(
        contexto, "quero reservar o salao-de-festas para 2030-04-20"
    )
    assert pendencia.acao == "criar_reserva", pendencia.acao
    # A Garantia 1 antes de qualquer aprovação: pedir NÃO grava.
    _sem_reserva_do_salao(contexto, "2030-04-20")


@given(parsers.parse("uma confirmação pendente de visitante na sessão do {apartamento}"))
def _pendencia_de_visitante(contexto, apartamento, aplicacao):
    from tests.conftest import rodar

    contexto["apartamento"] = apartamento
    contexto["sessao"] = rodar(
        aplicacao.state.servico_sessao.criar_sessao(apartamento)
    )
    pendencia = _pendencia_de(
        contexto, "libere a entrada de Joana Ribeiro em 2030-04-21"
    )
    assert pendencia.acao == "autorizar_visitante", pendencia.acao


def _sem_reserva_do_salao(contexto, data: str) -> None:
    from tests.conftest import rodar

    reservas = rodar(
        contexto["repo"].listar_reservas_do_apartamento(contexto["apartamento"])
    )
    iguais = [
        r for r in reservas
        if r.area == "salao-de-festas" and r.data.isoformat() == data
    ]
    assert not iguais, (
        f"a reserva foi gravada ANTES da aprovação: {[r.codigo for r in iguais]}. "
        "A Garantia 1 caiu."
    )


@when("o morador aprova pela rota de confirmações")
def _aprova(contexto):
    from tests.conftest import rodar

    contexto["resultado_aprovacao"] = rodar(
        contexto["app"].state.conversa.responder_confirmacao(
            contexto["sessao"], contexto["pendencia"].id, True
        )
    )


@then("a reserva é criada exatamente uma vez")
def _reserva_uma_vez(contexto):
    from tests.conftest import rodar

    reservas = rodar(
        contexto["repo"].listar_reservas_do_apartamento(contexto["apartamento"])
    )
    iguais = [
        r for r in reservas
        if r.area == "salao-de-festas" and r.data.isoformat() == "2030-04-20"
    ]
    assert len(iguais) == 1, (
        f"esperava exatamente 1 reserva do salão em 2030-04-20, achei "
        f"{len(iguais)} ({[r.codigo for r in iguais]}). Zero significa que a "
        "retomada não executou — a falha silenciosa que o enunciado chama de "
        "armadilha mais cara."
    )


@then("a autorização é criada exatamente uma vez")
def _autorizacao_uma_vez(contexto):
    from tests.conftest import rodar

    visitantes = rodar(
        contexto["repo"].listar_visitantes_do_apartamento(contexto["apartamento"])
    )
    iguais = [
        v for v in visitantes
        if v.nome == "Joana Ribeiro" and v.data.isoformat() == "2030-04-21"
    ]
    assert len(iguais) == 1, (
        f"esperava 1 autorização de Joana Ribeiro, achei {len(iguais)}. "
        "É o especialista de Visitantes que tem de retomar, e com DOIS agentes "
        "de confirmação o roteador precisa acertar entre eles (risco do ADR-0007)."
    )


@then("a resposta traz uma confirmação pendente")
def _traz_pendencia(contexto):
    assert contexto["pendentes"], (
        "nenhuma pendência foi criada. Se o morador escreveu 'já estou "
        "confirmando', a ação tinha de ficar pendente de qualquer forma."
    )


@then(parsers.parse("{nome} não aparece nos visitantes do {apartamento}"))
def _visitante_ausente(contexto, nome, apartamento):
    from tests.conftest import rodar

    visitantes = rodar(
        contexto["repo"].listar_visitantes_do_apartamento(apartamento)
    )
    achados = [v for v in visitantes if nome.lower() in v.nome.lower()]
    assert not achados, (
        f"{nome} foi autorizado sem aprovação pela rota: {achados}. "
        "Dizer 'já estou confirmando' não pode executar nada."
    )


@when("a resposta traz uma confirmação pendente")
def _quando_traz_pendencia(contexto):
    _traz_pendencia(contexto)
    contexto["detalhes"] = contexto["pendentes"][0].detalhes


# ──────────────────────────────────────────── o 409, por HTTP (@api)


@pytest.fixture
def cliente_http(aplicacao):
    """Cliente ASGI sobre a aplicação real. O `409` só existe nesta camada.

    ⚠️ **Usado como context manager, e isso é obrigatório aqui.** Fora do
    `with`, o `TestClient` monta um portal — e um event loop — **por
    requisição**. A primeira chamada prende a conexão interna do
    `DatabaseSessionService` ao loop dela; a segunda roda noutro loop e morre
    com `got Future attached to a different loop`.

    Estes dois cenários fazem três requisições cada (criar sessão, pedir o
    salão, aprovar), então o erro era garantido. Os nossos engines não têm esse
    problema porque usam `NullPool` (ADR-0014); o do ADK não é nosso.

    É o mesmo erro que já apareceu duas vezes neste projeto, pela terceira
    porta: pool de conexão e event loop não se misturam.
    """
    from fastapi.testclient import TestClient

    with TestClient(aplicacao) as cliente:
        yield cliente


def _abrir_sessao_http(cliente, apartamento: str) -> str:
    resposta = cliente.post("/sessoes", json={"apartamento": apartamento})
    assert resposta.status_code == 201, resposta.text
    return resposta.json()["session_id"]


def _pedir_salao_http(cliente, session_id: str, data: str) -> str:
    resposta = cliente.post(
        f"/sessoes/{session_id}/mensagens",
        json={"texto": f"quero reservar o salao-de-festas para {data}"},
    )
    assert resposta.status_code == 200, resposta.text
    pendentes = resposta.json()["confirmacoes_pendentes"]
    assert len(pendentes) == 1, f"esperava 1 pendência, veio {pendentes}"
    return pendentes[0]["id"]


@given("uma confirmação de reserva já aprovada")
def _ja_aprovada(contexto, cliente_http):
    sessao = _abrir_sessao_http(cliente_http, "101")
    identificador = _pedir_salao_http(cliente_http, sessao, "2030-04-20")

    resposta = cliente_http.post(
        f"/sessoes/{sessao}/confirmacoes",
        json={"id": identificador, "confirmado": True},
    )
    assert resposta.status_code == 200, resposta.text

    contexto["sessao_http"] = sessao
    contexto["id_pendencia"] = identificador
    contexto["apartamento"] = "101"


@when("o morador reenvia a mesma resposta com o mesmo id")
def _reenvia(contexto, cliente_http):
    contexto["resposta_http"] = cliente_http.post(
        f"/sessoes/{contexto['sessao_http']}/confirmacoes",
        json={"id": contexto["id_pendencia"], "confirmado": True},
    )


@given("uma confirmação pendente numa sessão de outro apartamento")
def _pendencia_de_outra_sessao(contexto, cliente_http):
    # A pendência nasce na sessão do 302; quem vai tentar responder é o 101.
    alheia = _abrir_sessao_http(cliente_http, "302")
    contexto["id_pendencia"] = _pedir_salao_http(cliente_http, alheia, "2030-08-15")
    contexto["sessao_http"] = _abrir_sessao_http(cliente_http, "101")
    contexto["apartamento"] = "101"


@when("o morador responde esse id na sua própria sessão")
def _responde_id_alheio(contexto, cliente_http):
    contexto["resposta_http"] = cliente_http.post(
        f"/sessoes/{contexto['sessao_http']}/confirmacoes",
        json={"id": contexto["id_pendencia"], "confirmado": True},
    )


@then(parsers.parse("a API responde {codigo:d}"))
def _api_responde(contexto, codigo):
    resposta = contexto["resposta_http"]
    assert resposta.status_code == codigo, (
        f"esperava {codigo}, veio {resposta.status_code}: {resposta.text}"
    )


@then("continua existindo exatamente uma reserva")
def _continua_uma(contexto, repo):
    from tests.conftest import rodar

    reservas = rodar(repo.listar_reservas_do_apartamento("101"))
    iguais = [
        r for r in reservas
        if r.area == "salao-de-festas" and r.data.isoformat() == "2030-04-20"
    ]
    assert len(iguais) == 1, (
        f"o reenvio mudou o número de reservas: {len(iguais)}. O passo 8 do "
        "avaliador confere exatamente isso."
    )


@then("nada é executado")
def _nada_executado(contexto, repo):
    from tests.conftest import rodar

    # A pendência era do 302, sobre o salão em 2030-08-15. Nenhuma reserva
    # nessa data pode existir, em apartamento nenhum.
    for numero in ("101", "302"):
        reservas = rodar(repo.listar_reservas_do_apartamento(numero))
        iguais = [r for r in reservas if r.data.isoformat() == "2030-08-15"]
        assert not iguais, (
            f"responder um id de outra sessão executou a ação para o {numero}: "
            f"{[r.codigo for r in iguais]}"
        )
