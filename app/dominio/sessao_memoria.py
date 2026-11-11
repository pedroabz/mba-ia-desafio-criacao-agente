"""Implementação TEMPORÁRIA de `ServicoSessao`, em memória.

⚠️  TEMPORÁRIA DE PROPÓSITO. A Fase 0 / Fase 2 do `TODO.md` substitui esta
classe por um `SessionService` do Google ADK (provavelmente o
`DatabaseSessionService` sobre Postgres), e nenhuma rota precisa mudar por isso
— é o motivo de a seam `ServicoSessao` existir.

O que ela NÃO resolve (e por isso não pode ficar):
  * Garantia 3 (nada se perde no reinício): memória morre com o processo, então
    o passo 13 do fluxo do avaliador reprovaria.
  * Os eventos reais da conversa: aqui nada escreve eventos ainda, porque quem
    os gera é o `Runner` do ADK (task 3.2).
"""

from __future__ import annotations

import asyncio
import uuid

from app.dominio.sessao import EventoSessao, Sessao, SessaoNaoEncontrada


class ServicoSessaoEmMemoria:
    """Sessões e eventos guardados em dicionários na memória do processo.

    Implementa `app.dominio.sessao.ServicoSessao`.
    """

    def __init__(self) -> None:
        self._sessoes: dict[str, Sessao] = {}
        # A ordem de inserção da lista É a ordem dos eventos exigida pelo
        # contrato ("em ordem").
        self._eventos: dict[str, list[EventoSessao]] = {}
        self._trava = asyncio.Lock()

    async def criar_sessao(self, apartamento: str) -> Sessao:
        # GARANTIA 2: o apartamento entra na sessão aqui e em nenhum outro
        # lugar. `Sessao` é frozen e não existe método de atualização.
        sessao = Sessao(id=str(uuid.uuid4()), apartamento=apartamento)
        async with self._trava:
            self._sessoes[sessao.id] = sessao
            self._eventos[sessao.id] = []
        return sessao

    async def buscar_sessao(self, session_id: str) -> Sessao | None:
        return self._sessoes.get(session_id)

    async def listar_eventos(self, session_id: str) -> list[EventoSessao]:
        if session_id not in self._sessoes:
            raise SessaoNaoEncontrada(session_id)
        return list(self._eventos[session_id])

    # -- apoio interno ------------------------------------------------------

    async def registrar_evento(self, session_id: str, evento: EventoSessao) -> None:
        """Acrescenta um evento ao fim do histórico da sessão.

        Não faz parte da interface `ServicoSessao`: no desenho definitivo quem
        grava eventos é o `Runner` do ADK, não a nossa camada de API. Existe
        aqui apenas para exercitar a rota de eventos enquanto a Fase 2 não
        chega.
        """
        if session_id not in self._sessoes:
            raise SessaoNaoEncontrada(session_id)
        async with self._trava:
            self._eventos[session_id].append(evento)
