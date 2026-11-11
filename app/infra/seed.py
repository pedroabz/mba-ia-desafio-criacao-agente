"""Carrega o estado inicial do condomínio de `dados/` para o Postgres.

É também o comando de restauração: semear de novo devolve reservas e visitantes
ao que os arquivos dizem.

REGRA ABSOLUTA: `dados/` é **somente leitura**. O enunciado exige que esses
arquivos fiquem byte-idênticos aos do repositório base, e o passo 15 do
avaliador confere. Nada aqui abre arquivo para escrita.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.dominio.regulamento import fatiar_em_artigos
from app.dominio.repositorio_memoria import carregar_dados_iniciais
from app.infra.embeddings import ClienteEmbedding


def _como_literal_de_vetor(vetor: list[float]) -> str:
    """`[0.1, 0.2]` -> `'[0.1,0.2]'`, que é o formato textual do `pgvector`.

    O vetor vai como texto e o SQL faz `CAST(:v AS vector)`. A alternativa
    seria registrar o codec do `pgvector` no `asyncpg`, que com `NullPool` é
    por conexão — mais peça móvel para nada, num caminho que roda uma vez por
    restauração.
    """
    return "[" + ",".join(repr(float(x)) for x in vetor) + "]"


async def semear_regulamento(
    engine: AsyncEngine,
    caminho_regulamento: Path,
    cliente: ClienteEmbedding,
) -> int:
    """Fatia o regulamento em artigos, gera os vetores e grava.

    ADR-0015, ADR-0016 e ADR-0020. Devolve quantos trechos foram gravados.

    Os 96 artigos saem em **uma** requisição ao modelo: o SDK transforma a
    lista numa só chamada a `:batchEmbedContents` (spike 2.4, achado 9). É por
    isso que a geração é um `await` só, e não um laço.
    """
    markdown = caminho_regulamento.read_text(encoding="utf-8")
    trechos = fatiar_em_artigos(markdown)
    if not trechos:
        raise RuntimeError(
            f"nenhum artigo encontrado em {caminho_regulamento}. O fatiador "
            "espera artigos como `**Art. 1º** ...` sob `## Capítulo N: ...`."
        )

    vetores = await cliente.gerar_de_documentos([t.texto_para_vetor for t in trechos])

    async with engine.begin() as c:
        # Regravado inteiro a cada restauração, como a tabela de áreas: o
        # regulamento é referência imutável vinda de `dados/`, e meia tabela
        # velha com meia nova produziria busca que mistura dois recortes.
        await c.execute(text("DELETE FROM regulamento_trecho"))
        for trecho, vetor in zip(trechos, vetores, strict=True):
            await c.execute(
                text(
                    "INSERT INTO regulamento_trecho (titulo, capitulo, texto, embedding) "
                    "VALUES (:t, :c, :x, CAST(:v AS vector))"
                ),
                {
                    "t": trecho.titulo,
                    "c": trecho.capitulo,
                    "x": trecho.texto,
                    "v": _como_literal_de_vetor(vetor),
                },
            )
    return len(trechos)


async def semear(engine: AsyncEngine, diretorio_dados: Path, *, limpar: bool = True) -> None:
    """Carrega `dados/*.json` para o banco.

    **Pressupõe o schema aplicado** (`banco.aplicar_schema`). A separação é
    deliberada: estrutura e dados têm donos diferentes e ciclos diferentes —
    a estrutura é criada uma vez, os dados são recarregados quantas vezes se
    quiser. Misturar as duas faria a restauração parecer responsável pelo
    schema, que é justamente a confusão que o ADR-0006 resolve.

    Args:
        limpar: apaga reservas e autorizações antes de recarregar. É o
            comportamento de restauração. Note que apagar aqui é legítimo e
            não contraria o ADR-0001: aquele ADR proíbe exclusão física como
            efeito de um **cancelamento**, porque o código precisa continuar
            conhecido. Restaurar é outra coisa — é voltar o mundo ao estado
            inicial, onde aqueles códigos nunca existiram.
    """
    dados = carregar_dados_iniciais(diretorio_dados)

    async with engine.begin() as c:
        if limpar:
            await c.execute(text("DELETE FROM autorizacao_entrada"))
            await c.execute(text("DELETE FROM reserva"))

        # Referência: apagada e regravada para não divergir de dados/ (ADR-0002).
        await c.execute(text("DELETE FROM area"))
        await c.execute(text("DELETE FROM apartamento"))

        for ap in dados.apartamentos:
            await c.execute(
                text("INSERT INTO apartamento (numero, morador) VALUES (:n, :m)"),
                {"n": ap.numero, "m": ap.morador},
            )
        for area in dados.areas:
            await c.execute(
                text("INSERT INTO area (id, nome, taxa) VALUES (:i, :n, :t)"),
                {"i": area.id, "n": area.nome, "t": area.taxa},
            )
        for reserva in dados.reservas:
            await c.execute(
                text(
                    "INSERT INTO reserva (codigo, apartamento, area, data, ativa) "
                    "VALUES (:c, :ap, :a, :d, 1)"
                ),
                {
                    "c": reserva.codigo,
                    "ap": reserva.apartamento,
                    "a": reserva.area,
                    "d": reserva.data.isoformat(),
                },
            )
        for visitante in dados.visitantes:
            await c.execute(
                text(
                    "INSERT INTO autorizacao_entrada (apartamento, nome, data) "
                    "VALUES (:ap, :n, :d)"
                ),
                {
                    "ap": visitante.apartamento,
                    "n": visitante.nome,
                    "d": visitante.data.isoformat(),
                },
            )
