"""O agente principal e a montagem da árvore.

ADR-0009. O principal **roteia e nada mais**: nenhuma ferramenta que toque o
banco, e o regulamento **fora** das instruções.

As duas restrições são do enunciado, e o **passo 15 do avaliador confere lendo
o código**:

- **sem ferramenta de domínio** (Garantia 2, `I-02`): se o principal pudesse
  ler ou gravar reserva, a fronteira entre especialistas viraria sugestão. O
  risco real não é ele fazer algo errado — é alguém dar a ele uma ferramenta de
  leitura "só para economizar uma transferência";
- **sem o regulamento nas instruções** (Garantia 4): o texto do regulamento no
  prompt do principal acompanharia **todas** as mensagens da sessão, inclusive
  as que não têm nada a ver com ele.

O que ele tem são duas coisas: os dois especialistas transacionais como
`sub_agents`, e o de Regulamento como `AgentTool`.
"""

from __future__ import annotations

from google.adk.agents.llm_agent import LlmAgent
from google.adk.models.base_llm import BaseLlm
from google.adk.tools.agent_tool import AgentTool

from app.agentes.especialistas import (
    criar_especialista_de_regulamento,
    criar_especialista_de_reservas,
    criar_especialista_de_visitantes,
)
from app.agentes.modelo import criar_modelo
from app.dominio.repositorio import RepositorioCondominio
from app.infra.recuperacao import RecuperadorDeRegulamento

INSTRUCAO_PRINCIPAL = """\
Você é o assistente do Residencial Aurora e fala com um morador pelo chat.

Seu trabalho é entender o que ele quer e encaminhar para quem resolve. Você
mesmo não consulta nem altera nada.

- reservar, cancelar, consultar disponibilidade ou listar reservas de áreas
  comuns (salão de festas, churrasqueira, quadra) -> transfira para `reservas`
- autorizar a entrada de visitante, ou listar visitantes -> transfira para
  `visitantes`
- dúvida sobre as regras do condomínio (horários, animais, silêncio, garagem,
  mudanças, obras, uso das áreas comuns) -> use a ferramenta `regulamento`

Se o pedido não for nenhuma dessas coisas, responda que você cuida de reservas,
visitantes e dúvidas sobre o regulamento, e pergunte o que ele precisa. Não
transfira e não chame ferramenta por pedido fora desses assuntos.

Atenda **um** pedido por mensagem: o que o morador acabou de escrever. Encaminhe
para um especialista só.

Se o histórico tiver uma ação aguardando aprovação do morador, ela **não é sua
responsabilidade e já está encaminhada**. Não a repita, não a encaminhe de novo
e não chame especialista por causa dela. Ela só sai do ar quando o morador
responde pelo canal de confirmações, que não passa por você.

Nunca invente o resultado de uma ação. Quem executa são os especialistas, e o
que eles disserem é o que vale.

Ao repassar a resposta de um especialista, **preserve o que ela cita**: o número
do artigo do regulamento, o código da reserva, a área e a data. Resumir é bom;
apagar a referência não — é por ela que o morador confere a regra.

Você fala com o morador em português, de forma breve e direta.
"""
# ⚠️ Os dois parágrafos acima sobre "um pedido por mensagem" e "ação aguardando
# aprovação" são de QUALIDADE DE ROTEAMENTO, não de garantia — e a distinção
# importa num projeto cuja tese é que regra em prompt não conta.
#
# O que eles corrigem, medido durante o P3 do plano 4: com uma confirmação
# aberta no histórico, o principal chamava OS DOIS especialistas de uma vez
# (`CALL:reservas | CALL:regulamento`). O ramo de reservas reemitia a
# confirmação pendente e interrompia a invocação; o ramo do regulamento era
# descartado pelo ADK ("Dropping function calls with no matching function
# response"), e a pergunta do morador ficava SEM RESPOSTA.
#
# Nenhuma garantia dependia disso: a Garantia 1 se manteve o tempo todo —
# `require_confirmation` é mecanismo do ADK, nada foi gravado, e a pendência
# duplicada era inócua. O que estava quebrado era o morador não ser atendido.
# Comportamento de conversa é exatamente o que pertence à instrução; se o
# modelo desobedecer, o pior caso é uma pendência a mais na lista.


def criar_agente_principal(
    repositorio: RepositorioCondominio,
    recuperador: RecuperadorDeRegulamento,
    taxas: dict[str, float],
    modelo: BaseLlm | None = None,
) -> LlmAgent:
    """Monta a árvore inteira e devolve a raiz.

    As taxas vêm de fora, já carregadas: é o retrato imutável do ADR-0013,
    lido do banco **uma vez** na subida. O portão de confirmação consulta esse
    mapa em memória e nunca o banco, para não ter caminho de erro.
    """
    # UM objeto de modelo, compartilhado pelos quatro agentes. É a Opção A do
    # ADR-0017 em forma de código: não há como dois agentes divergirem de
    # modelo, porque há um só.
    #
    # O parâmetro existe para os cenários de quota apontarem o modelo a um stub
    # que responde `429` — sem ele, não há como exercitar o caminho de erro sem
    # esgotar quota de verdade.
    modelo = modelo or criar_modelo()

    reservas = criar_especialista_de_reservas(repositorio, taxas, modelo)
    visitantes = criar_especialista_de_visitantes(repositorio, modelo)
    regulamento = criar_especialista_de_regulamento(recuperador, modelo)

    return LlmAgent(
        name="principal",
        model=modelo,
        instruction=INSTRUCAO_PRINCIPAL,
        # ⚠️ A assimetria abaixo é a decisão do ADR-0008, não descuido.
        #
        # `sub_agents` para quem confirma: `AgentTool` descartaria a sessão
        # aninhada e a pendência nunca chegaria à API (restrição `R1`).
        #
        # `AgentTool` para o Regulamento: é o que isola os events internos
        # dele da sessão principal, que é o que a Garantia 4 exige.
        sub_agents=[reservas, visitantes],
        tools=[AgentTool(agent=regulamento)],
        # O principal não tem `on_tool_error_callback` de domínio a tratar —
        # a única ferramenta dele é o especialista de Regulamento, que tem o
        # seu próprio. Registrar aqui também capturaria o erro já tratado lá.
    )
