"""A ferramenta do especialista de Regulamento.

Uma só: `buscar_no_regulamento`. Ela não confirma nada — consultar texto não
gera cobrança nem libera acesso —, e é por isso que o especialista que a
hospeda pode ser `AgentTool` (restrição `R3`, ADR-0008). Agente com ferramenta
que confirma não pode, e essa é a diferença que separa este especialista dos
outros dois.

**O que esta ferramenta devolve é a Garantia 4 em forma de retorno.** O
enunciado proíbe que um evento da sessão contenha trechos de capítulos que
tratam de outros assuntos. O recorte acontece aqui, **antes** de o modelo ver
qualquer coisa: no máximo 3 artigos, cada um com o seu capítulo, nunca um
capítulo inteiro e nunca o documento (ADR-0021).
"""

from __future__ import annotations

from typing import Any

from google.adk.tools.function_tool import FunctionTool

from app.infra.recuperacao import RecuperadorDeRegulamento

# O que a ferramenta diz ao modelo quando nada passou do corte. É mensagem
# para o MODELO, não para o morador — quem escreve a frase que o morador lê é
# o agente. A regra `A-5` (nenhuma frase nossa no campo `resposta` da API) vale
# na camada da rota, não aqui: uma ferramenta que devolvesse lista vazia e nada
# mais deixaria o modelo adivinhar se a busca falhou ou se não há regra.
AVISO_SEM_RESULTADO = (
    "Nenhum artigo do regulamento trata desse assunto. Diga ao morador que "
    "isso não está no regulamento do condomínio; não invente uma regra."
)


def criar_ferramentas_de_regulamento(
    recuperador: RecuperadorDeRegulamento,
) -> list[FunctionTool]:
    """Monta a ferramenta com o recuperador já ligado.

    A injeção por fechamento existe pelo mesmo motivo das outras ferramentas:
    para a função ter **apenas** os parâmetros que o modelo deve ver. Receber o
    recuperador como argumento o colocaria na declaração enviada ao modelo.
    """

    async def buscar_no_regulamento(assunto: str, tool_context: Any) -> dict[str, Any]:
        """Procura no regulamento interno os artigos sobre um assunto.

        Use para qualquer dúvida sobre as regras do condomínio: horários,
        animais, silêncio, garagem, mudanças, obras, uso das áreas comuns.

        Args:
            assunto: o que o morador quer saber, com as palavras dele.
        """
        artigos = await recuperador.buscar(assunto)

        if not artigos:
            # Lista vazia é resultado legítimo, não erro (ADR-0021). Devolver
            # o artigo menos distante aqui seria o modo de falha que o corte
            # existe para impedir.
            return {"artigos": [], "aviso": AVISO_SEM_RESULTADO}

        # ⚠️ A projeção é o recorte. Só estes três campos saem, e nunca o
        # capítulo inteiro: é o que mantém a Garantia 4 e o invariante `I-05`.
        # A similaridade NÃO sai — ela é diagnóstico nosso, e um número solto
        # no contexto só convida o modelo a comentá-lo.
        return {
            "artigos": [
                {
                    "artigo": artigo.titulo,
                    "capitulo": artigo.capitulo,
                    "texto": artigo.texto,
                }
                for artigo in artigos
            ]
        }

    return [FunctionTool(buscar_no_regulamento)]
