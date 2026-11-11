"""Passos dos cenários `@ferramenta`.

As ferramentas são chamadas **diretamente**, com um `ToolContext` de teste —
sem agente, sem modelo, sem chave de API. O que está sob teste é o contrato
delas: o que aceitam, o que devolvem e o que recusam.

O contexto é um objeto mínimo com `.state`, porque é a única coisa que as
ferramentas usam dele (o apartamento da sessão). Que o ADK injeta o
`ToolContext` de verdade e o mantém fora da declaração enviada ao modelo foi
verificado à parte, no spike 1.3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pytest
from pytest_bdd import given, parsers, then, when

from app.agentes.ferramentas.reservas import criar_ferramentas_de_reserva
from app.agentes.ferramentas.visitantes import criar_ferramentas_de_visitante
from app.agentes.portao import carregar_taxas, portao_de_reserva, portao_de_visitante


@dataclass
class ContextoDeTeste:
    """O mínimo que as ferramentas usam de um `ToolContext`."""

    state: dict[str, Any] = field(default_factory=dict)


# ------------------------------------------------------------------ fixtures


@pytest.fixture
def ferramentas(repo, contexto):
    """As sete ferramentas, indexadas por nome, com o portão ligado."""
    from tests.conftest import rodar

    taxas = rodar(carregar_taxas(repo))
    contexto["taxas"] = taxas
    todas = criar_ferramentas_de_reserva(repo, portao_de_reserva(taxas))
    todas += criar_ferramentas_de_visitante(repo, portao_de_visitante())
    return {t.name: t for t in todas}


def _chamar(ferramentas, contexto, _ferramenta: str, **argumentos):
    """Invoca a função por trás da ferramenta e guarda o retorno."""
    from tests.conftest import rodar

    ctx = ContextoDeTeste(state={"apartamento": contexto.get("apartamento", "101")})
    funcao = ferramentas[_ferramenta].func
    contexto["retorno"] = rodar(funcao(tool_context=ctx, **argumentos))
    return contexto["retorno"]


# -------------------------------------------------------------------- Dado


@given(parsers.parse("que o {apartamento} cancelou a reserva da quadra em {data}"))
def _cancelou_quadra(repo, contexto, apartamento, data):
    from datetime import date as _date

    from tests.conftest import rodar

    rodar(
        repo.cancelar_reserva_por_area_data(
            apartamento, "quadra", _date.fromisoformat(data)
        )
    )
    contexto["apartamento"] = apartamento


# ------------------------------------------------------------------- Quando


@when(parsers.parse('a ferramenta de reserva é chamada com a quadra em "{data}"'))
def _reserva_quadra_tool(ferramentas, contexto, data):
    _chamar(ferramentas, contexto, "criar_reserva", area="quadra", data=data)


@when(parsers.parse('a ferramenta de reserva é chamada com a área "{area}"'))
def _reserva_area_tool(ferramentas, contexto, area):
    _chamar(ferramentas, contexto, "criar_reserva", area=area, data="2030-05-02")


@when(parsers.parse('a ferramenta de disponibilidade é chamada com a área "{area}"'))
def _disponibilidade_area(ferramentas, contexto, area):
    _chamar(
        ferramentas, contexto, "consultar_disponibilidade", area=area, data="2030-05-02"
    )


@when(parsers.parse('a ferramenta de disponibilidade é chamada com o salão em "{data}"'))
def _disponibilidade_salao(ferramentas, contexto, data):
    _chamar(
        ferramentas,
        contexto,
        "consultar_disponibilidade",
        area="salao-de-festas",
        data=data,
    )


@when("a ferramenta de cancelamento por área e data é chamada")
def _cancelar_area_data_sem_args(ferramentas, contexto):
    _chamar(
        ferramentas,
        contexto,
        "cancelar_reserva_por_area_e_data",
        area="churrasqueira",
        data="2030-07-01",
    )


@when(
    parsers.parse(
        'a ferramenta de cancelamento por área e data é chamada com a quadra em "{data}"'
    )
)
def _cancelar_area_data(ferramentas, contexto, data):
    _chamar(
        ferramentas, contexto, "cancelar_reserva_por_area_e_data", area="quadra", data=data
    )


@when(parsers.parse('a ferramenta de cancelamento por código é chamada com "{codigo}"'))
def _cancelar_codigo(ferramentas, contexto, codigo):
    _chamar(ferramentas, contexto, "cancelar_reserva_por_codigo", codigo=codigo)


@when(
    parsers.parse(
        'a ferramenta de cancelamento por código é chamada com "{codigo}" numa sessão do {apartamento}'
    )
)
def _cancelar_codigo_alheio(ferramentas, contexto, codigo, apartamento):
    contexto["apartamento"] = apartamento
    _chamar(ferramentas, contexto, "cancelar_reserva_por_codigo", codigo=codigo)


@when("a ferramenta de listar reservas é chamada")
def _listar_reservas_tool(ferramentas, contexto):
    _chamar(ferramentas, contexto, "listar_minhas_reservas")


@when("a ferramenta de listar visitantes é chamada")
def _listar_visitantes_tool(ferramentas, contexto):
    _chamar(ferramentas, contexto, "listar_meus_visitantes")


@when(
    parsers.parse(
        'a ferramenta de autorizar visitante é chamada com {nome} em "{data}"'
    )
)
def _autorizar_tool(ferramentas, contexto, nome, data):
    contexto["nome_visitante"] = nome
    contexto["data_visita"] = data
    _chamar(ferramentas, contexto, "autorizar_visitante", nome=nome, data=data)


@when(parsers.parse("o portão de confirmação é consultado para {alvo}"))
def _consulta_portao(ferramentas, contexto, alvo):
    mapa = {
        "o salão de festas": ("criar_reserva", {"area": "salao-de-festas", "data": "2030-04-20"}),
        "a quadra": ("criar_reserva", {"area": "quadra", "data": "2030-04-06"}),
        "uma autorização de entrada": (
            "autorizar_visitante",
            {"nome": "Joana Ribeiro", "data": "2030-04-21"},
        ),
    }
    nome, args = mapa[alvo]
    from tests.conftest import rodar

    ctx = ContextoDeTeste(state={"apartamento": "101"})
    contexto["exige"] = rodar(
        ferramentas[nome].check_require_confirmation(args, ctx)  # type: ignore[arg-type]
    )


# -------------------------------------------------------------------- Então


@then("a reserva é criada para 2030-04-06")
def _reserva_criada_na_data(contexto):
    assert contexto["retorno"].get("criada") is True, contexto["retorno"]
    assert contexto["retorno"]["data"] == "2030-04-06"


@then("a chamada devolve uma recusa legível")
@then("a chamada devolve uma recusa dizendo que a área não é reservável")
@then("devolve uma recusa dizendo que a área não é reservável")
def _recusa_legivel(contexto):
    retorno = contexto["retorno"]
    assert "erro" in retorno, f"esperava recusa, veio {retorno}"
    assert retorno["erro"], "a recusa precisa ter mensagem"


@then("nenhuma exceção escapa da ferramenta")
def _sem_excecao(contexto):
    # Se tivesse escapado, o passo `Quando` já teria falhado — a asserção
    # existe para deixar a intenção explícita no cenário.
    assert contexto["retorno"] is not None


@then("a recusa carrega as áreas que podem ser reservadas")
def _recusa_com_areas(contexto):
    validas = contexto["retorno"].get("areas_validas")
    assert validas, contexto["retorno"]
    assert "quadra" in validas


@then("a chamada não responde que a data está livre")
def _nao_responde_livre(contexto):
    assert contexto["retorno"].get("livre") is not True, contexto["retorno"]


@then("o retorno diz apenas que a data está ocupada")
def _apenas_ocupada(contexto):
    assert contexto["retorno"] == {"livre": False}, contexto["retorno"]


@then("o retorno não contém o código da reserva nem o número do apartamento dono")
def _retorno_sem_dono(contexto):
    bruto = str(contexto["retorno"])
    assert "RSV-" not in bruto
    assert "302" not in bruto


@then(parsers.parse("a quadra em {data} some das reservas do {apartamento}"))
def _quadra_sumiu_tool(repo, data, apartamento):
    from tests.conftest import rodar

    reservas = rodar(repo.listar_reservas_do_apartamento(apartamento))
    assert not [
        r for r in reservas if r.area == "quadra" and r.data.isoformat() == data
    ], f"a quadra em {data} ainda consta"


@then(parsers.parse("a {codigo} some das reservas do {apartamento}"))
def _codigo_sumiu_tool(repo, codigo, apartamento):
    from tests.conftest import rodar

    reservas = rodar(repo.listar_reservas_do_apartamento(apartamento))
    assert codigo not in {r.codigo for r in reservas}


@then(parsers.parse("nenhuma reserva do {apartamento} é alterada"))
def _nenhuma_alterada_tool(repo, contexto, apartamento):
    from tests.conftest import rodar

    assert "erro" in contexto["retorno"], contexto["retorno"]
    reservas = rodar(repo.listar_reservas_do_apartamento(apartamento))
    assert contexto["codigo"] in {r.codigo for r in reservas}


@then("o retorno identifica a área e a data canceladas")
def _retorno_identifica(contexto):
    retorno = contexto["retorno"]
    assert retorno.get("cancelada") is True, retorno
    assert retorno.get("area") and retorno.get("data")


@then("o retorno não confirma nem nega a existência dessa reserva")
def _retorno_opaco(contexto):
    retorno = contexto["retorno"]
    assert "erro" in retorno, retorno
    assert "302" not in str(retorno)
    assert "RSV-4821" not in str(retorno)


@then(parsers.parse("o retorno traz a reserva da quadra do {apartamento}"))
def _traz_quadra(contexto, apartamento):
    areas = {r["area"] for r in contexto["retorno"]["reservas"]}
    assert "quadra" in areas, contexto["retorno"]


@then(parsers.parse("não traz nenhuma reserva do {apartamento}"))
def _nao_traz_de_outro(contexto, apartamento):
    assert "RSV-4821" not in str(contexto["retorno"])


@then("o retorno não traz essa reserva")
def _nao_traz_cancelada(contexto):
    datas = {r["data"] for r in contexto["retorno"]["reservas"]}
    assert "2030-03-09" not in datas, contexto["retorno"]


@then("o retorno é um dicionário com chave nomeada")
def _dicionario_nomeado(contexto):
    assert isinstance(contexto["retorno"], dict)
    assert len(contexto["retorno"]) == 1


@then(parsers.parse('a chave não é "{proibida}"'))
def _chave_nao_e(contexto, proibida):
    assert proibida not in contexto["retorno"]


@then(parsers.parse("a lista de visitantes traz {nome}"))
def _traz_visitante(contexto, nome):
    nomes = {v["nome"] for v in contexto["retorno"]["visitantes"]}
    assert nome in nomes, contexto["retorno"]


@then("não traz visitante de outro apartamento")
def _sem_visitante_alheio(contexto):
    nomes = {v["nome"] for v in contexto["retorno"]["visitantes"]}
    assert "Paulo Nogueira" not in nomes


@then("a autorização é criada")
def _autorizacao_criada(contexto):
    assert contexto["retorno"].get("autorizado") is True, contexto["retorno"]


@then("chamar de novo com os mesmos dados devolve uma recusa legível")
def _duplicata_recusada(ferramentas, contexto):
    retorno = _chamar(
        ferramentas,
        contexto,
        "autorizar_visitante",
        nome=contexto["nome_visitante"],
        data=contexto["data_visita"],
    )
    assert "erro" in retorno, retorno


@then(parsers.parse("o {apartamento} continua com exatamente uma autorização para {nome}"))
def _uma_autorizacao_tool(repo, apartamento, nome):
    from tests.conftest import rodar

    visitantes = rodar(repo.listar_visitantes_do_apartamento(apartamento))
    assert len([v for v in visitantes if v.nome == nome]) == 1


@then("ele decide que a ação exige confirmação")
def _exige_confirmacao(contexto):
    assert contexto["exige"] is True


@then("ele decide que a ação não exige confirmação")
def _nao_exige_confirmacao(contexto):
    assert contexto["exige"] is False
