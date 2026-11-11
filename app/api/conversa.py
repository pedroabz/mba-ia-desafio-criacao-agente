"""O miolo das rotas de conversa: roda o turn e monta a resposta.

Quatro regras do spike 3.2 moram aqui, e **nenhuma é detalhe de
implementação**. Cada uma existe porque a alternativa foi medida e dá errado:

| | Regra | O que acontece sem ela |
|---|---|---|
| `A-7` | os events são lidos **até o fim** | erro de quota vira `200` com resposta vazia, que é o sinal de "confirmação pendente" |
| `A-9` | só o texto do **principal** vai em `resposta` | o morador recebe duas respostas concatenadas, a do especialista e a do roteador |
| `A-5` | nenhuma frase **nossa** em `resposta` | vazio deixa de ser informação, e o avaliador não consegue distinguir "parou para confirmar" de "respondeu" |
| `A-3` | a lista de pendências é montada **depois** do turn | pendência criada no meio do turn não aparece |
"""

from __future__ import annotations

from dataclasses import dataclass, field

from google.adk.runners import Runner
from google.genai import types

from app.api.pendencias import (
    NOME_DA_CHAMADA_DE_CONFIRMACAO,
    confirmacoes_abertas,
    esta_aberta,
)
from app.dominio.sessao import ConfirmacaoPendente, Sessao
from app.infra.sessao_adk import NOME_DA_APLICACAO, ServicoSessaoADK

NOME_DO_AGENTE_PRINCIPAL = "principal"
"""Quem fala com o morador. `A-9`."""


class ConfirmacaoNaoPendente(LookupError):
    """Esse `id` não está esperando aprovação nesta conversa.

    Cobre os três casos que o contrato manda recusar com `409`: `id` que não
    existe, `id` de outra sessão e `id` **já respondido**. São o mesmo caso por
    baixo (`A-2`), e nenhum deles executa nada.
    """

    def __init__(self, identificador: str) -> None:
        super().__init__(identificador)
        self.identificador = identificador


@dataclass(frozen=True, slots=True)
class ResultadoDaConversa:
    """O que a rota devolve: o texto e o que ficou pendente."""

    resposta: str
    confirmacoes_pendentes: list[ConfirmacaoPendente] = field(default_factory=list)


class Conversa:
    """Executa um turn e devolve o que a API publica."""

    def __init__(self, runner: Runner, sessoes: ServicoSessaoADK) -> None:
        self._runner = runner
        self._sessoes = sessoes

    async def enviar_texto(self, sessao: Sessao, texto: str) -> ResultadoDaConversa:
        """Uma mensagem do morador.

        ⚠️ **Mensagem de texto NUNCA aprova nada** (`A-4`). Mesmo que o morador
        escreva *"sim, confirmo"*, isto é um pedido novo: o único caminho que
        retoma uma ação pendente é a rota de confirmações, com um
        `FunctionResponse` autorado por `"user"`. Medido no spike 3.2 — e é o
        que o passo 11 do avaliador testa.
        """
        mensagem = types.Content(role="user", parts=[types.Part(text=texto)])
        return await self._rodar(sessao, mensagem)

    async def responder_confirmacao(
        self, sessao: Sessao, identificador: str, confirmado: bool
    ) -> ResultadoDaConversa:
        """Aprova ou nega uma pendência, e retoma a execução.

        ⚠️ **A aprovação é um `FunctionResponse` autorado por `"user"`, nunca
        texto** (restrição `R5`, medida no spike R1). Reusar o caminho da rota
        de mensagens **não retoma nada**: o texto é lido como pedido novo, nasce
        uma segunda pendência e a ação original continua esperando.

        O nome do `FunctionResponse` tem de ser `adk_request_confirmation` e o
        `id` o da chamada de confirmação — é assim que o processador do ADK
        encontra a ação a reexecutar.

        Levanta `ConfirmacaoNaoPendente` quando o `id` não está esperando
        aprovação nesta conversa. A rota traduz isso em `409`.
        """
        # ⚠️ `A-1` — A CHECAGEM VEM ANTES DE ACIONAR O ADK. Depois é tarde:
        # medido no spike 3.2, um `id` que o ADK não reconhece faz ele quebrar
        # com `ValueError`, e a rota responde `500`. O passo 9 do roteiro
        # reprova nisso.
        #
        # ⚠️ `A-2` — É UMA PERGUNTA SÓ. O contrato manda recusar três casos
        # (`id` inexistente, `id` de outra sessão, `id` já respondido), e a
        # tentação é escrever três checagens. Medido: nos três o `id`
        # simplesmente não está na lista de pendências desta conversa. Três
        # checagens seriam três chances de divergir.
        if not esta_aberta(
            await self._sessoes.eventos_do_adk(sessao.id, sessao.apartamento),
            identificador,
        ):
            raise ConfirmacaoNaoPendente(identificador)

        aprovacao = types.Content(
            role="user",
            parts=[
                types.Part(
                    function_response=types.FunctionResponse(
                        id=identificador,
                        name=NOME_DA_CHAMADA_DE_CONFIRMACAO,
                        response={"confirmed": confirmado},
                    )
                )
            ],
        )
        return await self._rodar(sessao, aprovacao)

    async def _rodar(
        self, sessao: Sessao, mensagem: types.Content
    ) -> ResultadoDaConversa:
        """Roda o turn, drena os events e monta a resposta."""
        falas_do_principal: list[str] = []

        # ⚠️ `A-7` — ESTE LAÇO VAI ATÉ O FIM, DE PROPÓSITO.
        #
        # Não ponha `break` aqui. O `Runner` do ADK, quando o modelo falha por
        # quota, primeiro EMITE um evento com `error_code='RESOURCE_EXHAUSTED'`
        # e só DEPOIS levanta a exceção — o `raise` está depois do `yield`
        # (`_finalizer.py:579`). Quem para no evento de erro não vê exceção
        # nenhuma, monta uma resposta vazia e devolve `200`.
        #
        # E `resposta` vazia é, pelo contrato do enunciado, o sinal de "parei
        # esperando confirmação". Uma falha de quota se disfarçaria de
        # pendência. É a restrição `M-4`, e o cenário
        # `Quota esgotada nunca vira resposta vazia` existe só para isso.
        async for evento in self._runner.run_async(
            user_id=sessao.apartamento,
            session_id=sessao.id,
            new_message=mensagem,
        ):
            # ⚠️ `A-9` — só o principal fala com o morador.
            #
            # Com `mode="single_turn"`, o especialista produz o texto dele e o
            # principal produz o seu. Os dois viram evento. Concatenar entrega
            # a mesma coisa dita duas vezes; e o ADR-0008 escolheu
            # `single_turn` justamente para o principal fechar o turno.
            if getattr(evento, "author", None) != NOME_DO_AGENTE_PRINCIPAL:
                continue
            conteudo = getattr(evento, "content", None)
            for parte in getattr(conteudo, "parts", None) or []:
                if parte.text:
                    falas_do_principal.append(parte.text)

        # ⚠️ `A-3` — depois do turn, varrendo a conversa inteira. Uma pendência
        # nasce no meio do turn; montar a lista durante o laço pegaria o estado
        # de antes.
        eventos = await self._sessoes.eventos_do_adk(sessao.id, sessao.apartamento)

        # ⚠️ `A-5` — se o principal não falou, `resposta` fica VAZIA.
        #
        # Nunca ponha uma frase nossa aqui, nem "aguardando confirmação", nem
        # "ok". O vazio É a informação: pelo contrato, ele significa que o fluxo
        # parou esperando aprovação. Texto fabricado pelo nosso código no campo
        # onde o modelo escreve embaralha quem disse o quê — e o avaliador lê
        # esse campo.
        return ResultadoDaConversa(
            resposta="".join(falas_do_principal),
            confirmacoes_pendentes=confirmacoes_abertas(eventos),
        )

    async def pendencias(self, sessao: Sessao) -> list[ConfirmacaoPendente]:
        """As pendências da conversa, sem rodar turn nenhum."""
        eventos = await self._sessoes.eventos_do_adk(sessao.id, sessao.apartamento)
        return confirmacoes_abertas(eventos)


def construir_runner(agente_principal, servico_adk) -> Runner:
    """Monta o `Runner` com o `App`, sem resumability.

    ⚠️ **Sem `ResumabilityConfig(is_resumable=True)`** — decisão `R1/D-04`. Não
    é esquecimento: ligar habilitaria retomar uma invocação que morreu no meio
    de um turn, o ADK documenta isso como *best-effort* e **exige tools
    idempotentes**. Nenhuma das sete ferramentas foi escrita pensando nisso, e
    nada no roteiro do avaliador exige o recurso.
    """
    from google.adk.apps.app import App

    return Runner(
        app=App(name=NOME_DA_APLICACAO, root_agent=agente_principal),
        session_service=servico_adk,
    )
