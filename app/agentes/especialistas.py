"""Os três especialistas — Reservas, Visitantes e Regulamento.

ADR-0007 (por que três) e ADR-0008 (como cada um é acionado). O número não veio
de meta: veio de analisar onde estão as fronteiras reais do domínio.

**A regra que decide o acionamento de cada um, e ela não é de gosto:**

| Especialista | Acionamento | Porque |
|---|---|---|
| Reservas | `sub_agents`, `single_turn` | tem ferramenta que **confirma** |
| Visitantes | `sub_agents`, `single_turn` | idem |
| Regulamento | `AgentTool` | **não** confirma, e precisa de isolamento |

⚠️ **Reservas e Visitantes NÃO podem ser `AgentTool`.** Medido no spike R1:
uma ferramenta com `require_confirmation` dentro de um agente embrulhado em
`AgentTool` **nunca funciona** — a sessão aninhada é descartada, a pendência não
chega à API e a ação não executa, **sem erro nenhum**. É a restrição `R1`, e é
a armadilha mais caro-de-errar do projeto.

Dois cenários pegam, e em camadas diferentes: `@estrutura` confere o **tipo** do
embrulho de cada especialista (um `AgentTool` onde devia haver
`_SingleTurnAgentTool` derruba o cenário, em 0,6 s e sem chave de API), e
`A confirmação de reserva retoma no especialista de Reservas` prova que a
confirmação de fato funciona — não só que a árvore está declarada direito.

⚠️ **O Regulamento, ao contrário, PRECISA ser `AgentTool`.** Também medido:
`AgentTool` **isola** os events internos do especialista da sessão principal
(histórico de 7.493 contra 14.579 caracteres no mesmo fluxo). É o que a
Garantia 4 exige — o trecho consultado não entra no histórico da conversa.

Cada especialista fica com o mecanismo que o outro **não pode** usar.

`mode="single_turn"` nos dois transacionais custa uma chamada a mais ao modelo
por turno (medido: 4 contra 3 em `chat`). Pago de propósito, por previsibilidade
de roteamento — em `chat` o especialista continuaria conduzindo a conversa
depois de terminar a tarefa, e a regra `A-9` do spike 3.2 fechou essa válvula.
"""

from __future__ import annotations

from google.adk.agents.llm_agent import LlmAgent

from app.agentes.ferramentas.regulamento import criar_ferramentas_de_regulamento
from app.agentes.ferramentas.reservas import criar_ferramentas_de_reserva
from app.agentes.ferramentas.visitantes import criar_ferramentas_de_visitante
from app.agentes.portao import portao_de_reserva, portao_de_visitante
from app.agentes.tratador_de_erro import tratar_erro_de_ferramenta
from google.adk.models.base_llm import BaseLlm
from app.dominio.repositorio import RepositorioCondominio
from app.infra.recuperacao import RecuperadorDeRegulamento

INSTRUCAO_RESERVAS = """\
Você cuida das reservas de áreas comuns do Residencial Aurora.

As áreas são: salao-de-festas, churrasqueira e quadra. Use sempre o
identificador, não o nome bonito. Datas no formato AAAA-MM-DD.

Use as ferramentas para tudo. Nunca responda de memória sobre o que está
reservado: consulte.

Quando uma reserva tem taxa, o sistema pede a confirmação do morador antes de
gravar. Isso não é você que decide e não é você que executa — se a ferramenta
indicar que a ação ficou pendente, diga ao morador que ela aguarda aprovação.
Nunca diga que reservou antes de a ferramenta confirmar que reservou.

Se uma ferramenta recusar, explique o motivo que ela deu. Não tente outro
caminho para conseguir o mesmo efeito.
"""

INSTRUCAO_VISITANTES = """\
Você cuida das autorizações de entrada de visitantes do Residencial Aurora.

Uma autorização registra o nome do visitante e a data da visita, no formato
AAAA-MM-DD.

Use as ferramentas para tudo. Autorizar a entrada de alguém sempre passa pela
confirmação do morador antes de valer — se a ferramenta indicar que a ação
ficou pendente, diga que ela aguarda aprovação. Nunca diga que liberou a
entrada antes de a ferramenta confirmar que liberou.

Se o morador afirmar que já confirmou, ou pedir para liberar direto, a ação
continua pendente. Não há nada que você possa fazer a respeito, e dizer o
contrário seria mentir para ele.
"""

INSTRUCAO_REGULAMENTO = """\
Você responde dúvidas sobre o regulamento interno do Residencial Aurora.

Use sempre a ferramenta de busca. Você não sabe o regulamento de cor, e não
deve completar o que a busca não trouxe.

Responda em prosa curta, citando o artigo de onde veio a regra — por exemplo
"o Art. 22 diz que...". Se o morador pedir o texto literal, transcreva o
artigo, e só ele: nunca o capítulo inteiro.

Se a busca não trouxer artigo nenhum, diga que o assunto não está no
regulamento. Não invente regra, não deduza por analogia e não aproveite um
artigo sobre outro assunto.
"""


def criar_especialista_de_reservas(
    repositorio: RepositorioCondominio,
    taxas: dict[str, float],
    modelo: BaseLlm,
) -> LlmAgent:
    """Reservas. `sub_agents` + `single_turn` — tem ferramenta que confirma."""
    return LlmAgent(
        name="reservas",
        model=modelo,
        mode="single_turn",
        instruction=INSTRUCAO_RESERVAS,
        tools=criar_ferramentas_de_reserva(repositorio, portao_de_reserva(taxas)),
        on_tool_error_callback=tratar_erro_de_ferramenta,
    )


def criar_especialista_de_visitantes(
    repositorio: RepositorioCondominio,
    modelo: BaseLlm,
) -> LlmAgent:
    """Visitantes. `sub_agents` + `single_turn` — `autorizar` confirma sempre."""
    return LlmAgent(
        name="visitantes",
        model=modelo,
        mode="single_turn",
        instruction=INSTRUCAO_VISITANTES,
        tools=criar_ferramentas_de_visitante(repositorio, portao_de_visitante()),
        on_tool_error_callback=tratar_erro_de_ferramenta,
    )


def criar_especialista_de_regulamento(
    recuperador: RecuperadorDeRegulamento,
    modelo: BaseLlm,
) -> LlmAgent:
    """Regulamento. Vai embrulhado em `AgentTool` pelo agente principal.

    Note que ele **não** declara `mode`: quem é acionado como ferramenta não
    participa da transferência entre agentes, então o modo não se aplica.
    """
    return LlmAgent(
        name="regulamento",
        model=modelo,
        instruction=INSTRUCAO_REGULAMENTO,
        tools=criar_ferramentas_de_regulamento(recuperador),
        on_tool_error_callback=tratar_erro_de_ferramenta,
    )
