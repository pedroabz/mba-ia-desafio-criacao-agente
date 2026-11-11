"""Interface (seam) do serviço de sessão, e os modelos de sessão do domínio.

Este módulo define **só o contrato**. As rotas dependem desta interface e nunca
de uma implementação concreta.

Por que a seam existe
---------------------
O serviço de sessão definitivo será o `SessionService` do Google ADK (Fase 0 /
Fase 2 do `TODO.md`), com persistência — a Garantia 3 exige que a sessão
sobreviva ao reinício da API, e o enunciado avisa que a retomada de confirmação
muda de comportamento conforme o serviço de sessão usado. Como esse spike ainda
não rodou, as rotas da task 3.1 conversam com esta interface e a Fase 2 troca
**apenas a implementação**.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable


class SessaoNaoEncontrada(LookupError):
    """Levantada quando o `session_id` pedido não existe.

    A camada de API traduz esta exceção em `404` — o contrato manda que *toda*
    rota com `{session_id}` no caminho responda `404` quando a sessão não
    existe (conferido no passo 9 do fluxo do avaliador).
    """

    def __init__(self, session_id: str) -> None:
        super().__init__(session_id)
        self.session_id = session_id


@dataclass(frozen=True, slots=True)
class Sessao:
    """Uma conversa de um morador.

    GARANTIA 2 — `apartamento` é definido **uma única vez**, na criação, e
    representa o morador autenticado. A dataclass é `frozen` e a interface
    `ServicoSessao` **não tem** nenhuma operação que altere o apartamento de
    uma sessão existente: não há caminho de código, nem a pedido do modelo nem
    a pedido do morador, que troque esse valor depois. Daqui para frente, as
    tools da Fase 2 leem o apartamento daqui (via state da sessão), nunca de um
    parâmetro escolhido pelo modelo.
    """

    id: str
    apartamento: str
    criada_em: datetime = field(
        default_factory=lambda: datetime.now(tz=timezone.utc), compare=False
    )


@dataclass(frozen=True, slots=True)
class EventoSessao:
    """Um evento gravado na sessão.

    `GET /sessoes/{session_id}/eventos` devolve "todos os eventos gravados na
    sessão, em ordem, com o conteúdo completo de cada um". Por isso o modelo é
    deliberadamente aberto:

      * `id`, `autor` e `timestamp` são os metadados que a API sempre expõe;
      * `conteudo` é um dicionário livre que carrega o payload inteiro do
        evento.

    Quando a Fase 2 trocar esta seam pelo `SessionService` do ADK, cada `Event`
    do ADK entra aqui com `conteudo = evento_adk.model_dump(mode="json")` — ou
    seja, texto do morador, resposta do agente, chamadas de tool, respostas de
    tool e pedidos de confirmação cabem em `conteudo` sem que o formato da
    resposta HTTP mude. O passo 12 do fluxo do avaliador inspeciona exatamente
    isso: os eventos precisam incluir as chamadas de tool da conversa.
    """

    id: str
    autor: str
    timestamp: datetime
    conteudo: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ConfirmacaoPendente:
    """Uma ação aguardando a resposta do morador pela rota de confirmações.

    Forma exigida pelo contrato: `id`, `acao` e `detalhes` (cujo conteúdo é
    livre, mas precisa trazer área+data para reserva e nome+data para
    visitante — passos 7 e 11).

    # TODO: task 3.2 / Fase 0 — de onde estas pendências são derivadas (eventos
    # do ADK? tabela própria? qual `id` é estável entre requests e sobrevive ao
    # reinício?) é a saída do spike da Fase 0. Nesta task o modelo existe só
    # para fixar o formato da resposta.
    """

    id: str
    acao: str
    detalhes: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class ServicoSessao(Protocol):
    """Criação, consulta e histórico das sessões de conversa."""

    async def criar_sessao(self, apartamento: str) -> Sessao:
        """Cria uma sessão nova para o apartamento informado.

        O apartamento é gravado no state da sessão aqui, e só aqui
        (Garantia 2). Devolve a sessão criada, com o `session_id` gerado.
        """
        ...

    async def buscar_sessao(self, session_id: str) -> Sessao | None:
        """Devolve a sessão, ou `None` se ela não existir.

        Devolve `None` em vez de levantar exceção porque este é o método usado
        pela checagem de existência que precede *toda* rota com `{session_id}`.
        """
        ...

    async def listar_eventos(self, session_id: str) -> list[EventoSessao]:
        """Todos os eventos da sessão, em ordem de gravação.

        Levanta `SessaoNaoEncontrada` se a sessão não existir.
        """
        ...
