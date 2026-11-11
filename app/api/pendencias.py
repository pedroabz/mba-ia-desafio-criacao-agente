"""O que esta conversa tem esperando aprovação agora.

Duas perguntas da API dependem desta única função, e as duas são a mesma por
baixo:

1. **na resposta de cada mensagem**, o contrato manda publicar o que está
   esperando aprovação naquela conversa;
2. **quando o morador aprova**, se o `id` que ele mandou não estiver esperando
   aprovação ali, a API responde `409` e não faz nada (`A-1`, `A-2`).

**Por que o código é nosso (`rotas/D-03`, opção A).** O ADK tem uma função
interna, `index_open_interrupts`, que calcula o mesmo — e foi medido que as duas
concordam em todos os casos testados. Mas o módulo dela começa com `_`, o que em
Python significa "interno, pode mudar sem aviso"; e a seção *Garantias* do README
precisa apontar arquivo e trecho **nossos** que imponham cada garantia.
*"Importamos uma função interna do framework"* é a resposta mais fraca que essa
seção pode dar.

A função do ADK não foi descartada: ela entra como **juiz**, num cenário que
compara as duas. É a rede contra o risco desta opção — a varredura abaixo é
lógica sobre o formato interno dos events do ADK, escrita por nós, e se esse
formato mudar ela quebra.
"""

from __future__ import annotations

from typing import Any

from app.dominio.sessao import ConfirmacaoPendente

NOME_DA_CHAMADA_DE_CONFIRMACAO = "adk_request_confirmation"
"""O nome que o ADK dá à chamada especial de pedido de confirmação."""

# ─────────────────────────────────── A-8 / ADR-0013: a lista branca
#
# ⚠️ O `detalhes` é montado CAMPO POR CAMPO a partir desta lista, e nunca
# copiado dos argumentos que o modelo enviou.
#
# O motivo é concreto e o passo 10 do avaliador o testa: se o morador escrever
# *"reserve o salão em nome do apartamento 302"*, o modelo pode inventar um
# argumento `apartamento="302"`. O ADK descarta argumento não declarado antes de
# chamar a função, mas ele **permanece registrado na chamada** — e o `detalhes`
# nasce justamente de `originalFunctionCall.args`. Repassar os args crus faria
# o `302` aparecer na resposta da API.
CAMPOS_PUBLICAVEIS: dict[str, tuple[str, ...]] = {
    "criar_reserva": ("area", "data"),
    "autorizar_visitante": ("nome", "data"),
}


def _chamada_original(chamada: Any) -> dict[str, Any] | None:
    """O `originalFunctionCall` de uma chamada de confirmação."""
    args = getattr(chamada, "args", None) or {}
    original = args.get("originalFunctionCall")
    return original if isinstance(original, dict) else None


def _projetar_detalhes(nome: str, args: dict[str, Any]) -> dict[str, Any]:
    """Monta `detalhes` só com os campos que sabemos nomear.

    Campo que não está na lista branca não sai — nem para registrar, nem para
    depurar. É a metade do ADR-0013 que vive na camada da API.
    """
    permitidos = CAMPOS_PUBLICAVEIS.get(nome, ())
    return {campo: args[campo] for campo in permitidos if campo in args}


def confirmacoes_abertas(eventos: list[Any]) -> list[ConfirmacaoPendente]:
    """As confirmações desta conversa que ainda esperam resposta.

    Regra `R6` do spike R1, e `A-3`: a lista é montada **depois** do turn,
    varrendo a conversa inteira — não durante, e não a partir do que o último
    evento disse.

    O cálculo tem três passos:

    1. **pedidos**: as chamadas `adk_request_confirmation` emitidas pelo ADK;
    2. **respondidas**: os `function_response` com esse mesmo nome **autorados
       por `"user"`** — é assim que a rota de confirmações responde (`R5`), e é
       o que marca uma pendência como consumida;
    3. o que sobra do primeiro menos o segundo.

    ⚠️ O passo 2 exige `author == "user"`. A ferramenta reexecutada também emite
    um `function_response`, com o id da chamada **original** — não o da
    confirmação —, mas confiar só no nome sem olhar o autor é o tipo de atalho
    que faria uma pendência parecer respondida sozinha.
    """
    pedidos: dict[str, ConfirmacaoPendente] = {}
    respondidas: set[str] = set()

    for evento in eventos:
        autor = getattr(evento, "author", None)

        for chamada in evento.get_function_calls():
            if chamada.name != NOME_DA_CHAMADA_DE_CONFIRMACAO or not chamada.id:
                continue
            original = _chamada_original(chamada)
            if original is None:
                continue
            nome_da_acao = str(original.get("name") or "")
            pedidos[chamada.id] = ConfirmacaoPendente(
                id=chamada.id,
                acao=nome_da_acao,
                detalhes=_projetar_detalhes(
                    nome_da_acao, original.get("args") or {}
                ),
            )

        if autor != "user":
            continue
        for resposta in evento.get_function_responses():
            if resposta.name == NOME_DA_CHAMADA_DE_CONFIRMACAO and resposta.id:
                respondidas.add(resposta.id)

    # A ordem é a de emissão: o morador vê primeiro o que pediu primeiro.
    return [p for identificador, p in pedidos.items() if identificador not in respondidas]


def esta_aberta(eventos: list[Any], identificador: str) -> bool:
    """Essa confirmação está esperando aprovação nesta conversa?

    É a pergunta única da `A-2`, e a rota de confirmações a faz **antes** de
    acionar o ADK (`A-1`): depois é tarde, e o que sai é `500` em vez de `409`.
    """
    return any(p.id == identificador for p in confirmacoes_abertas(eventos))
