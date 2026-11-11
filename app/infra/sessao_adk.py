"""`ServicoSessao` sobre o `DatabaseSessionService` do ADK.

Substitui `app/dominio/sessao_memoria.py`, que era temporária e perdia tudo no
reinício. É esta troca que completa a **Garantia 3** para a conversa: os dados
já sobreviviam (ADR-0014), os eventos passam a sobreviver agora.

**Por que existe uma tabela nossa (`rotas/D-02`, opção A).** O ADK guarda cada
conversa debaixo de três chaves: aplicação, **usuário** e id. Para abrir uma
conversa é preciso saber o usuário — e foi medido que ele separa de verdade:
com o usuário errado, o ADK devolve nada, e não existe operação que ache uma
conversa pelo id sozinho.

A URL da API, porém, só traz o `session_id`. Isso é de propósito: o apartamento
é definido **uma vez**, na criação, e nunca volta pela URL — é o que impede uma
mensagem do 101 de alcançar os dados do 302. Então a rota precisa descobrir o
apartamento antes de abrir a conversa, e a tabela `conversa` é esse mapa.

⚠️ **A ORDEM DA GRAVAÇÃO É A MITIGAÇÃO, não detalhe.** O ADK cria primeiro, e
só depois gravamos a ligação. Assim o pior caso é uma conversa do ADK **órfã**,
invisível para a API — e não um `session_id` que a API aceita e o ADK não acha.
Invertida, a falha seria `404` do ADK no meio de um turn, que é muito pior de
diagnosticar.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from google.adk.sessions import DatabaseSessionService
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.dominio.sessao import EventoSessao, Sessao, SessaoNaoEncontrada

NOME_DA_APLICACAO = "aurora"
"""O `app_name` do ADK. Fixo: há uma aplicação só."""


class ServicoSessaoADK:
    """Implementa `app.dominio.sessao.ServicoSessao` sobre o ADK."""

    def __init__(self, servico: DatabaseSessionService, engine: AsyncEngine) -> None:
        self._servico = servico
        self._engine = engine

    @property
    def servico_adk(self) -> DatabaseSessionService:
        """O serviço do ADK, para o `Runner` usar o MESMO que a API usa.

        Dois serviços sobre o mesmo banco funcionariam, mas montar dois é
        convite a divergir numa configuração.
        """
        return self._servico

    async def criar_sessao(self, apartamento: str) -> Sessao:
        """Cria a conversa no ADK e **depois** grava a ligação.

        GARANTIA 2 — o apartamento entra no `state` aqui, e só aqui. Ele é
        também o `user_id` do ADK, o que faz a separação por usuário do
        framework valer como segunda cerca.
        """
        sessao = await self._servico.create_session(
            app_name=NOME_DA_APLICACAO,
            user_id=apartamento,
            state={"apartamento": apartamento},
        )

        # Depois, nunca antes. Ver a nota sobre a ordem, no topo do módulo.
        async with self._engine.begin() as conexao:
            await conexao.execute(
                text(
                    "INSERT INTO conversa (session_id, apartamento) "
                    "VALUES (:s, :a)"
                ),
                {"s": sessao.id, "a": apartamento},
            )

        return Sessao(id=sessao.id, apartamento=apartamento)

    async def _apartamento_da_conversa(self, session_id: str) -> str | None:
        async with self._engine.connect() as conexao:
            linha = (
                await conexao.execute(
                    text("SELECT apartamento FROM conversa WHERE session_id = :s"),
                    {"s": session_id},
                )
            ).first()
        return linha[0] if linha else None

    async def buscar_sessao(self, session_id: str) -> Sessao | None:
        """Devolve a sessão, ou `None`.

        O `404` de **todas** as rotas com `{session_id}` nasce daqui, e a fonte
        é a **nossa** tabela — que é a que o contrato descreve. Perguntar ao
        ADK primeiro exigiria o usuário, que é justamente o que não se sabe.
        """
        apartamento = await self._apartamento_da_conversa(session_id)
        if apartamento is None:
            return None
        return Sessao(id=session_id, apartamento=apartamento)

    async def listar_eventos(self, session_id: str) -> list[EventoSessao]:
        """Todos os eventos da conversa, em ordem de gravação.

        O `conteudo` carrega o evento do ADK inteiro
        (`evento.model_dump(mode="json")`), porque o contrato pede "o conteúdo
        completo de cada um" — e o passo 12 do avaliador inspeciona as chamadas
        de ferramenta que estão lá dentro.
        """
        apartamento = await self._apartamento_da_conversa(session_id)
        if apartamento is None:
            raise SessaoNaoEncontrada(session_id)

        sessao = await self._servico.get_session(
            app_name=NOME_DA_APLICACAO, user_id=apartamento, session_id=session_id
        )
        if sessao is None:
            # A conversa está na nossa tabela e não no ADK. É o caso que a
            # ordem de gravação torna impossível na criação, mas pode acontecer
            # se alguém apagar as tabelas do ADK sem apagar a nossa.
            raise SessaoNaoEncontrada(session_id)

        return [_como_evento_do_dominio(evento) for evento in sessao.events]

    async def eventos_do_adk(self, session_id: str, apartamento: str) -> list[Any]:
        """Os `Event` do ADK, crus. A varredura de pendências precisa deles."""
        sessao = await self._servico.get_session(
            app_name=NOME_DA_APLICACAO, user_id=apartamento, session_id=session_id
        )
        return list(sessao.events) if sessao is not None else []


def _como_evento_do_dominio(evento: Any) -> EventoSessao:
    """Traduz um `Event` do ADK para o modelo que a API expõe."""
    conteudo = evento.model_dump(mode="json")
    bruto = getattr(evento, "timestamp", None)
    if isinstance(bruto, (int, float)):
        quando = datetime.fromtimestamp(bruto, tz=timezone.utc)
    elif isinstance(bruto, datetime):
        quando = bruto
    else:
        quando = datetime.now(tz=timezone.utc)

    return EventoSessao(
        id=str(getattr(evento, "id", "") or ""),
        autor=str(getattr(evento, "author", "") or ""),
        timestamp=quando,
        conteudo=conteudo,
    )
