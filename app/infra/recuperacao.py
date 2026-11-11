"""Busca semântica no regulamento (ADR-0015, ADR-0016, ADR-0021).

A pergunta do morador vira vetor, e o Postgres devolve os artigos mais
próximos por cosseno. Três números governam, e os três são do ADR-0021:

    no máximo 3 artigos  ·  similaridade >= 0,65  ·  lista vazia se nenhum passa

**Os números foram medidos, não escolhidos.** Nove perguntas contra os 96
artigos reais: acertos dentro do escopo em 0,699–0,763, falsos positivos fora
do escopo em 0,556–0,598. O vão de 0,10 entre os dois é o que o corte de 0,65
divide.

⚠️ **O corte é o único mecanismo contra "achei errado".** Sem ele, *"quanto
custa o bitcoin hoje"* recebe o Art. 62 (Mudanças) com 0,5595 — e o morador lê
isso como resposta. "Achei errado" é pior que "não achei": o segundo o modelo
contorna, o primeiro chega como verdade. O cenário `Pergunta fora de escopo não
devolve trecho nenhum` existe só para isso.

⚠️ **Por que o corte NÃO é relativo ao melhor resultado.** Foi a alternativa
mais atraente e a medição a derrubou: pergunta fora de escopo produz três
quase-empates. No caso do bitcoin, o 1º e o 3º ficam a **0,37%** um do outro,
então um corte proporcional devolveria os três. Na pergunta da piscina, onde a
queda do 1º ao 3º é de 8,7%, o mesmo corte proporcional cortaria o segundo
artigo legítimo. O relativo é mais generoso justamente quando devia ser mais
severo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.infra.embeddings import ClienteEmbedding

# ADR-0021. Ficam aqui, nomeados, e não espalhados na consulta: são o conteúdo
# da decisão, e quem for mexer neles tem que passar pelo ADR.
MAXIMO_DE_ARTIGOS = 3
CORTE_DE_SIMILARIDADE = 0.65

# ADR-0022 — remissão explícita de capítulo. `Capítulo III`, `Capítulo XIII`.
_REMISSAO = re.compile(r"Cap[íi]tulo\s+([IVXLC]+)")

# Fim de frase: ponto ou ponto e vírgula seguidos de espaço. O regulamento usa
# os dois — "§ 1º ...; § 2º ..." aparece com ponto e vírgula.
_FIM_DE_FRASE = re.compile(r"(?<=[.;])\s+")


@dataclass(frozen=True, slots=True)
class ArtigoRecuperado:
    """Um artigo que a busca devolveu, com o quanto ele casou."""

    titulo: str
    """`Art. 22`."""

    capitulo: str
    """`Capítulo IV: Piscina`."""

    texto: str
    """O corpo do artigo, com parágrafos e incisos."""

    similaridade: float
    """Cosseno entre a pergunta e o artigo, de 0 a 1."""


def _como_literal_de_vetor(vetor: list[float]) -> str:
    """`[0.1, 0.2]` -> `'[0.1,0.2]'`, o formato textual do `pgvector`."""
    return "[" + ",".join(repr(float(x)) for x in vetor) + "]"


def _numeral(capitulo: str) -> str | None:
    """`Capítulo VIII: Animais` -> `VIII`."""
    achado = _REMISSAO.search(capitulo)
    return achado.group(1) if achado else None


def remissao_de_capitulo(artigo: ArtigoRecuperado) -> tuple[str, str] | None:
    """Acha a remissão a outro capítulo, e devolve `(numeral, frase)`.

    ADR-0022. O Art. 39 diz *"deve respeitar o período de silêncio previsto no
    Capítulo III"* e **não dá o horário** — quem dá é o Art. 16, de outro
    capítulo. Essa frase é o que liga os dois, e ela está escrita no documento:
    é sinal mecânico, não inferência de modelo.

    **A frase, e não o artigo inteiro.** Medido: usando o texto inteiro do
    Art. 39 como consulta, o Art. 16 ganha por 0,0018 — ruído. Usando a frase
    da remissão, ganha por 0,0127 e chega a 0,8114. A frase funciona porque
    **nomeia o conceito** ("o período de silêncio"), e o Art. 16 é quem o
    define.

    Devolve `None` quando não há remissão, ou quando a remissão é ao próprio
    capítulo do artigo — que não acrescenta nada.
    """
    proprio = _numeral(artigo.capitulo)
    for frase in _FIM_DE_FRASE.split(artigo.texto):
        achado = _REMISSAO.search(frase)
        if achado is None:
            continue
        numeral = achado.group(1)
        if numeral == proprio:
            continue
        return numeral, frase.strip()
    return None


class RecuperadorDeRegulamento:
    """Acha os artigos que respondem uma pergunta do morador."""

    def __init__(self, engine: AsyncEngine, cliente: ClienteEmbedding) -> None:
        self._engine = engine
        self._cliente = cliente

    async def buscar(self, assunto: str) -> list[ArtigoRecuperado]:
        """Devolve até 3 artigos acima do corte, do mais próximo ao menos.

        Lista vazia significa "não achei", e é um resultado legítimo — não um
        erro e não um caso a contornar devolvendo o melhor de qualquer jeito.

        Quando o artigo melhor colocado remete a outro capítulo, a busca
        **segue a remissão** e traz de lá o artigo que fecha a resposta
        (ADR-0022). Isso consome a última das três vagas; o total nunca passa
        de `MAXIMO_DE_ARTIGOS`.
        """
        principais = await self._por_similaridade(assunto, MAXIMO_DE_ARTIGOS)
        if not principais:
            return []

        remetido = await self._seguir_remissao(principais)
        if remetido is None:
            return principais

        # A vaga da remissão sai do FIM da lista: o artigo que a resposta
        # literalmente aponta vale mais que o terceiro palpite por
        # similaridade. E o teto de 3 do ADR-0021 continua valendo — este
        # passo não aumenta o recorte, só troca quem o ocupa.
        ja_tem = {a.titulo for a in principais}
        if remetido.titulo in ja_tem:
            return principais
        return principais[: MAXIMO_DE_ARTIGOS - 1] + [remetido]

    async def _seguir_remissao(
        self, principais: list[ArtigoRecuperado]
    ) -> ArtigoRecuperado | None:
        """Segue a remissão do artigo melhor colocado que tiver uma.

        **No máximo uma por busca**, de propósito: cada remissão custa uma
        chamada a mais ao modelo de embedding, e a quota diária é o limite mais
        apertado deste projeto. O melhor colocado é o escolhido porque é o mais
        relevante — se a resposta dele aponta para outro lugar, é esse ponteiro
        que importa.
        """
        for artigo in principais:
            remissao = remissao_de_capitulo(artigo)
            if remissao is None:
                continue
            numeral, frase = remissao
            achados = await self._por_similaridade(
                frase, limite=1, apenas_capitulo=numeral
            )
            return achados[0] if achados else None
        return None

    async def _por_similaridade(
        self, consulta: str, limite: int, apenas_capitulo: str | None = None
    ) -> list[ArtigoRecuperado]:
        """A consulta por proximidade, opcionalmente restrita a um capítulo."""
        # `RETRIEVAL_QUERY`, não `RETRIEVAL_DOCUMENT`: a pergunta do morador e
        # o texto do artigo são naturezas diferentes, e é para isso que os dois
        # valores existem (ADR-0020). Usar DOCUMENT aqui desfaz a assimetria em
        # silêncio — a busca continua respondendo, só pior.
        vetor = await self._cliente.gerar_de_consulta(consulta)
        parametros: dict[str, object] = {
            "vetor": _como_literal_de_vetor(vetor),
            "corte": CORTE_DE_SIMILARIDADE,
            "limite": limite,
        }

        filtro_de_capitulo = ""
        if apenas_capitulo is not None:
            # ⚠️ O `:` no padrão NÃO é enfeite. Sem ele, `Capítulo VI` casaria
            # com `Capítulo VIII`, porque "VIII" começa com "VI" — é o mesmo
            # bug de prefixo que derrubou um cenário durante esta
            # implementação. Numeral romano não se compara por prefixo.
            filtro_de_capitulo = "AND capitulo LIKE :capitulo "
            parametros["capitulo"] = f"Capítulo {apenas_capitulo}:%"

        # O operador `<=>` do pgvector é DISTÂNCIA de cosseno, então a
        # similaridade é `1 - distância`. O filtro vai no `WHERE` sobre a
        # mesma expressão, e não num `HAVING` ou num `if` em Python, para o
        # banco já devolver só o que passa.
        sql = text(
            "SELECT titulo, capitulo, texto, "
            "       1 - (embedding <=> CAST(:vetor AS vector)) AS similaridade "
            "FROM regulamento_trecho "
            "WHERE 1 - (embedding <=> CAST(:vetor AS vector)) >= :corte "
            f"{filtro_de_capitulo}"
            "ORDER BY embedding <=> CAST(:vetor AS vector) "
            "LIMIT :limite"
        )
        async with self._engine.connect() as conexao:
            linhas = (await conexao.execute(sql, parametros)).all()

        return [
            ArtigoRecuperado(
                titulo=linha[0],
                capitulo=linha[1],
                texto=linha[2],
                similaridade=float(linha[3]),
            )
            for linha in linhas
        ]
