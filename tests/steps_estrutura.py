"""Passos dos cenários `@estrutura` — inspecionam a ÁRVORE, não o comportamento.

Eles montam os quatro agentes e olham o que foi declarado: quais ferramentas
cada um tem, qual modelo, o que está nas instruções. **Nenhum chama o modelo**,
então rodam sem chave de API e ficam verdes antes dos `@conversa`.

É a mesma inspeção que o **passo 15 do avaliador** faz lendo o código — a
diferença é que aqui ela falha sozinha.

**Eles pegam a armadilha do `R1`, e isso foi uma surpresa boa.** O plano 4
supunha que não pegariam — "uma árvore errada ainda é uma árvore". Mas com
`mode="single_turn"` o ADK expõe os `sub_agents` em `tools`, e aí dá para
conferir o **tipo** do embrulho: um `AgentTool` onde devia haver
`_SingleTurnAgentTool` derruba o cenário. Verificado por sabotagem.

O ganho é de velocidade de diagnóstico: a falha mais caro-de-errar do projeto
aparece em **0,6 segundo, sem chave de API**.

O cenário `A confirmação de reserva retoma no especialista de Reservas`
continua necessário — ele prova que a confirmação **de fato funciona**, não só
que a árvore está declarada direito. São camadas diferentes da mesma defesa.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, then, when

from app.config import MODELO, MODELOS_CONHECIDOS

# As ferramentas que tocam o banco. Se o agente principal tiver qualquer uma
# delas, a Garantia 2 e o ADR-0009 caíram.
FERRAMENTAS_DE_RESERVA = frozenset({
    "consultar_disponibilidade",
    "listar_minhas_reservas",
    "criar_reserva",
    "cancelar_reserva_por_area_e_data",
    "cancelar_reserva_por_codigo",
})
FERRAMENTAS_DE_VISITANTE = frozenset({
    "listar_meus_visitantes",
    "autorizar_visitante",
})
FERRAMENTAS_DE_DOMINIO = FERRAMENTAS_DE_RESERVA | FERRAMENTAS_DE_VISITANTE


@pytest.fixture
def arvore(repo, contexto):
    """Os quatro agentes montados, indexados por nome.

    Usa o repositório real (schema próprio deste teste) porque as taxas do
    portão vêm da tabela de áreas. Nenhum modelo é chamado.
    """
    from app.agentes.portao import carregar_taxas
    from app.agentes.principal import criar_agente_principal
    from app.infra.recuperacao import RecuperadorDeRegulamento
    from tests.conftest import rodar
    from tests.embedding_de_teste import EmbeddingDeTeste

    rodar(_semear(repo))
    taxas = rodar(carregar_taxas(repo))

    # Cliente de embedding falso: montar a árvore não busca nada, e exigir
    # chave de API aqui tiraria estes cenários do grupo "roda sem chave".
    recuperador = RecuperadorDeRegulamento(repo._engine, EmbeddingDeTeste())
    principal = criar_agente_principal(repo, recuperador, taxas)

    agentes = {principal.name: principal}
    for sub in principal.sub_agents:
        agentes[sub.name] = sub
    # O de Regulamento não é sub_agent: ele está dentro de um AgentTool.
    for ferramenta in principal.tools:
        agente = getattr(ferramenta, "agent", None)
        if agente is not None:
            agentes[agente.name] = agente

    contexto["arvore"] = agentes
    contexto["principal"] = principal
    return agentes


async def _semear(repo):
    """Carrega as áreas, de onde o portão lê as taxas."""
    from pathlib import Path

    from app.infra.seed import semear

    raiz = Path(__file__).resolve().parent.parent
    await semear(repo._engine, raiz / "dados")


def _nomes_de_ferramenta(agente) -> set[str]:
    """Os nomes das ferramentas declaradas por um agente."""
    return {getattr(f, "name", getattr(f, "__name__", "")) for f in agente.tools}


# ------------------------------------------------------------------- Dado


@given("a árvore de agentes montada")
@given("o aplicativo montado com o agente principal e os três especialistas")
def _arvore_montada(arvore):
    assert set(arvore) == {"principal", "reservas", "visitantes", "regulamento"}, (
        f"esperava os quatro agentes, achei {sorted(arvore)}"
    )


# ------------------------------------------------------- fronteiras (ADR-0007)


@then("o especialista de Reservas não tem ferramenta de visitante")
def _reservas_sem_visitante(arvore):
    invasoras = _nomes_de_ferramenta(arvore["reservas"]) & FERRAMENTAS_DE_VISITANTE
    assert not invasoras, f"Reservas tem ferramenta de visitante: {invasoras}"


@then("o especialista de Visitantes não tem ferramenta de reserva")
def _visitantes_sem_reserva(arvore):
    invasoras = _nomes_de_ferramenta(arvore["visitantes"]) & FERRAMENTAS_DE_RESERVA
    assert not invasoras, f"Visitantes tem ferramenta de reserva: {invasoras}"


@then("o especialista de Regulamento não tem ferramenta que toque o banco")
def _regulamento_sem_dominio(arvore):
    invasoras = _nomes_de_ferramenta(arvore["regulamento"]) & FERRAMENTAS_DE_DOMINIO
    assert not invasoras, f"Regulamento tem ferramenta de domínio: {invasoras}"


# -------------------------------------------- o principal só roteia (ADR-0009)


@then("o agente principal não tem nenhuma ferramenta de domínio")
def _principal_sem_dominio(contexto):
    tem = _nomes_de_ferramenta(contexto["principal"]) & FERRAMENTAS_DE_DOMINIO
    assert not tem, (
        f"o agente principal tem ferramenta de domínio: {tem}. O ADR-0009 "
        "proíbe, e o passo 15 do avaliador confere isso lendo o código."
    )


@then("as ferramentas que ele tem são o especialista de Regulamento e a transferência")
def _principal_so_tem_regulamento(contexto):
    principal = contexto["principal"]

    # ⚠️ Com `mode="single_turn"`, o ADK **converte os sub_agents em
    # ferramentas** — `principal.tools` traz três itens, não um:
    #
    #   AgentTool             -> regulamento
    #   _SingleTurnAgentTool  -> reservas
    #   _SingleTurnAgentTool  -> visitantes
    #
    # Isso confirma o que o spike 2.4 mediu: em `single_turn` o especialista é
    # exposto ao principal como FUNÇÃO com o nome do agente, não como
    # `transfer_to_agent`. Os dois `_SingleTurnAgentTool` SÃO "a transferência"
    # que este cenário nomeia. A primeira versão deste passo exigia
    # `len(tools) == 1` e ficou vermelha com a árvore certa.
    #
    # O que importa cobrar, então, não é a contagem: é que **nenhuma** das
    # ferramentas do principal seja uma função de domínio. Toda ferramenta dele
    # tem que embrulhar um agente.
    sem_agente = [
        getattr(f, "name", repr(f))
        for f in principal.tools
        if getattr(f, "agent", None) is None
    ]
    assert not sem_agente, (
        f"o principal tem ferramenta que não embrulha agente: {sem_agente}. "
        "Toda ferramenta dele é um especialista; função própria é o que o "
        "ADR-0009 proíbe."
    )

    embrulhados = {f.agent.name for f in principal.tools}
    assert embrulhados == {"regulamento", "reservas", "visitantes"}, (
        f"esperava os três especialistas embrulhados, achei {sorted(embrulhados)}"
    )

    # E a distinção que o ADR-0008 decidiu: os dois transacionais são
    # `sub_agents` (o ADK os expõe como ferramenta por causa do modo), e o
    # Regulamento é `AgentTool` declarado por nós. Se Reservas aparecer como
    # `AgentTool` em vez de `_SingleTurnAgentTool`, a confirmação morre (R1).
    assert [s.name for s in principal.sub_agents] == ["reservas", "visitantes"], (
        "os dois transacionais precisam ser sub_agents — AgentTool mata a "
        f"confirmação (R1). Veio: {[s.name for s in principal.sub_agents]}"
    )
    from google.adk.tools.agent_tool import AgentTool

    por_nome = {f.agent.name: f for f in principal.tools}
    assert type(por_nome["regulamento"]) is AgentTool, (
        "o Regulamento tem que ser AgentTool declarado — é o que isola os "
        f"events dele da sessão (Garantia 4). Veio {type(por_nome['regulamento'])}"
    )
    for transacional in ("reservas", "visitantes"):
        assert type(por_nome[transacional]) is not AgentTool, (
            f"{transacional} está como AgentTool. A sessão aninhada é "
            "descartada, a pendência nunca chega à API e a ação não executa, "
            "SEM ERRO NENHUM. É a restrição R1."
        )


@when("as instruções do agente principal são inspecionadas")
def _inspeciona_instrucoes(contexto):
    contexto["instrucao"] = str(contexto["principal"].instruction)


@then("elas não contêm texto do regulamento")
def _instrucao_sem_regulamento(contexto):
    from pathlib import Path

    instrucao = contexto["instrucao"]
    raiz = Path(__file__).resolve().parent.parent
    regulamento = (raiz / "dados" / "regulamento.md").read_text(encoding="utf-8")

    # Marcadores que só existem no regulamento. Procurar por palavra genérica
    # daria falso positivo: a instrução legitimamente cita "animais" e
    # "garagem" para dizer ao principal quando transferir.
    for marca in ("Art. 1º", "Parágrafo único", "coleira refletiva", "§ 1º"):
        assert marca not in instrucao, (
            f"a instrução do principal contém {marca!r}, que é texto do "
            "regulamento. Garantia 4: o regulamento acompanharia TODAS as "
            "mensagens da sessão."
        )
    # E nenhum artigo inteiro, por mais curto que seja.
    for linha in regulamento.splitlines():
        trecho = linha.strip()
        if len(trecho) > 80:
            assert trecho not in instrucao, (
                f"a instrução contém uma linha literal do regulamento: {trecho[:60]!r}"
            )


# ------------------------------------------------- Garantia 2 / I-02 (passo 15)


@then("nenhuma ferramenta declara um parâmetro de apartamento")
def _nenhum_parametro_de_apartamento(arvore):
    import inspect

    achados = []
    for nome_do_agente, agente in arvore.items():
        for ferramenta in agente.tools:
            funcao = getattr(ferramenta, "func", None)
            if funcao is None:
                continue  # AgentTool não tem função própria
            for parametro in inspect.signature(funcao).parameters:
                if "apartamento" in parametro.lower():
                    achados.append(f"{nome_do_agente}.{ferramenta.name}({parametro})")

    assert not achados, (
        f"estas ferramentas declaram apartamento: {achados}. O apartamento vem "
        "do state da sessão (I-02, Garantia 2) — declarar como parâmetro o "
        "coloca na declaração enviada ao modelo, e aí ele pode escolher."
    )


# ------------------------------------------------------- modelo (ADR-0017)


def _nome_do_modelo(agente) -> str:
    """O nome do modelo, seja ele string ou objeto `Gemini`.

    Os agentes recebem um objeto `Gemini` construído, não a string: é o que
    permite injetar a chave de API (o ADK leria do `os.environ`, onde o `.env`
    não chega) e, no P5, o `retry_options`. Então `agente.model` é o objeto, e
    o nome está em `.model` dentro dele.
    """
    modelo = agente.model
    return str(getattr(modelo, "model", modelo))


@when("eu percorro todos os agentes da árvore")
def _percorro(arvore, contexto):
    contexto["modelos"] = {nome: _nome_do_modelo(a) for nome, a in arvore.items()}


@then("os quatro declaram exatamente o mesmo nome de modelo")
def _mesmo_modelo(contexto):
    distintos = set(contexto["modelos"].values())
    assert len(distintos) == 1, (
        f"os agentes usam modelos diferentes: {contexto['modelos']}. A Opção A "
        "do ADR-0017 foi escolhida pela uniformidade — com modelos diferentes, "
        "problema de roteamento se confunde com diferença de modelo."
    )


@then("esse nome é o que a configuração do projeto define num lugar só")
def _nome_vem_da_configuracao(contexto):
    for nome, modelo in contexto["modelos"].items():
        assert modelo == MODELO, (
            f"{nome} usa {modelo!r}, e a configuração define {MODELO!r}. "
            "Nome repetido fora de app/config.py é como a uniformidade se perde."
        )


@then('nenhum deles usa um modelo cujo nome case com "gemini-<n>.<n>-flash"')
def _nenhum_flash(contexto):
    import re

    # `gemini-3.8-flash` casa; `gemini-3.5-flash-lite` NÃO casa, por causa do
    # `$`. A diferença entre os dois é 20 requisições por dia contra 500.
    familia_flash = re.compile(r"^gemini-\d+\.\d+-flash$")
    maus = {n: m for n, m in contexto["modelos"].items() if familia_flash.match(str(m))}
    assert not maus, (
        f"estes agentes usam um Flash: {maus}. São 20 requisições por DIA no "
        "plano gratuito, contra 70-85 de uma correção (M-1)."
    )


@then('todos usam um modelo cujo nome termina em "-flash-lite"')
def _todos_flash_lite(contexto):
    maus = {
        n: m for n, m in contexto["modelos"].items()
        if not str(m).endswith("-flash-lite")
    }
    assert not maus, f"estes não são Flash-Lite: {maus}"


@then("cada um declara explicitamente o seu modelo")
def _modelo_explicito(arvore):
    # Um agente construído sem `model=` herda `LlmAgent.DEFAULT_MODEL`, que é
    # um Flash — e cair nele não emite aviso nenhum (M-2). A asserção é que o
    # valor declarado não é vazio e não é o default.
    for nome, agente in arvore.items():
        assert agente.model, f"{nome} não declara modelo"
        assert _nome_do_modelo(agente), f"{nome} tem modelo sem nome"


@then("nenhum modelo declarado é igual ao padrão do ADK")
def _nao_e_o_padrao(contexto):
    from google.adk.agents.llm_agent import LlmAgent

    padrao = LlmAgent.DEFAULT_MODEL
    maus = {n: m for n, m in contexto["modelos"].items() if str(m) == padrao}
    assert not maus, (
        f"estes agentes usam o padrão do ADK ({padrao!r}): {maus}. Ele roteia "
        "para gemini-3.8-flash, o balde de 20/dia, e cair nele é silencioso."
    )


@then("o modelo de cada um está na lista de modelos Gemini conhecidos do projeto")
def _modelo_conhecido(contexto):
    maus = {
        n: m for n, m in contexto["modelos"].items()
        if str(m) not in MODELOS_CONHECIDOS
    }
    assert not maus, (
        f"modelo fora da lista conhecida: {maus}. A lista é "
        f"{sorted(MODELOS_CONHECIDOS)} — ela pega erro de digitação (M-7), que "
        "o ADK aceita na construção e só quebra no primeiro 404, e modelo sem "
        "plano gratuito (M-3), que falharia na correção de quem não paga."
    )
