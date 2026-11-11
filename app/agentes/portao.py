"""O portão de confirmação — decide quais ações precisam da aprovação do morador.

ADR-0013. A Garantia 1 do enunciado exige que toda ação que **gera cobrança**
ou **libera acesso** fique pendente até o morador responder pela rota de
confirmações. No ADK isso é `require_confirmation`, que aceita uma função
decidindo caso a caso.

Duas coisas aqui não são detalhe de implementação:

**A taxa vem de um retrato imutável, não do banco.** Carregado na subida a
partir da tabela de áreas. O motivo é o modo de falha: uma leitura de banco
que falhe no instante da decisão degradaria para "não precisa confirmar" — e
a Garantia 1 cairia por um erro que não tem nada a ver com ela. Com o
retrato, o portão não tem como falhar.

A objeção de "duas fontes de verdade" não se aplica: a tabela de áreas são
três linhas que o seed escreve e ninguém mais toca. Um retrato dela é a mesma
verdade, não uma segunda.

**A função recebe os mesmos argumentos da ferramenta, inclusive
`tool_context`.** Verificado no spike R1: omiti-lo levanta `TypeError` em
tempo de execução, não na importação. E ela é invocada **4×** por reserva
aprovada — se levantar exceção durante a retomada, a ação nunca executa.
Por isso ela não faz I/O e não tem caminho de erro.
"""

from __future__ import annotations

from typing import Any, Callable

from app.dominio.repositorio import RepositorioCondominio


async def carregar_taxas(repositorio: RepositorioCondominio) -> dict[str, float]:
    """Lê a tabela de áreas uma vez e devolve o retrato `{area: taxa}`.

    Chamado na subida da aplicação. Depois disto, o portão nunca toca o banco.
    """
    return {area.id: area.taxa for area in await repositorio.listar_areas()}


def portao_de_reserva(taxas: dict[str, float]) -> Callable[..., bool]:
    """Devolve a função que o `require_confirmation` de `criar_reserva` usa.

    Regra de negócio 2: só área com taxa maior que zero gera cobrança. A
    quadra tem taxa 0 e **não** confirma (passo 6 do roteiro do avaliador);
    salão e churrasqueira confirmam (passo 7).

    Área desconhecida devolve `False` de propósito: quem recusa área
    inexistente é a ferramenta, com uma mensagem útil (ADR-0003). Confirmar
    uma reserva que vai ser recusada de qualquer forma só gastaria um turno
    do morador.
    """

    def exige_confirmacao(area: str, data: str, tool_context: Any = None) -> bool:
        return taxas.get(area, 0.0) > 0

    return exige_confirmacao


def portao_de_visitante() -> Callable[..., bool]:
    """Devolve a função que o `require_confirmation` de `autorizar_visitante` usa.

    Regra de negócio 3: autorizar um visitante libera a entrada de alguém no
    prédio. **Sempre** confirma — não há equivalente à taxa zero aqui
    (passo 11 do roteiro).
    """

    def exige_confirmacao(nome: str, data: str, tool_context: Any = None) -> bool:
        return True

    return exige_confirmacao
