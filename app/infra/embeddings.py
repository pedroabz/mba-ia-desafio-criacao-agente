"""Geração dos vetores do regulamento (ADR-0020).

O modelo é `gemini-embedding-001` com **768 dimensões**, e a assimetria da
busca é controlada por `task_type`:

    semear  -> RETRIEVAL_DOCUMENT
    buscar  -> RETRIEVAL_QUERY

Essa assimetria é o argumento que decidiu o ADR-0020, e não é sobre qualidade
de vetor: no `gemini-embedding-2` o tipo de tarefa é **prefixo de texto no
prompt**, enquanto aqui é **parâmetro**. Num projeto cuja tese é que regra em
prompt não conta, o mecanismo que o código controla é o coerente.

Medido contra o servidor em 2026-11-08, antes de haver vetor gravado:
768 dimensões confirmadas, uma lista de 3 textos devolve **3 vetores
distintos** (a armadilha `M-5` é do `-2`, não deste), e a pergunta *"até que
horas a piscina funciona?"* dá cosseno 0,774 contra o Art. 22 contra 0,54–0,57
nos outros dois — a busca separa.

A interface existe para a suíte poder semear **sem chave de API**: os cenários
do seed são `@storage`, e `@storage` significa "não precisa de modelo".
"""

from __future__ import annotations

import asyncio
import os
from typing import Protocol, runtime_checkable

MODELO = "gemini-embedding-001"
DIMENSOES = 768

# Os dois valores de `task_type`. Nomeados porque o cenário de regressão do
# ADR-0020 confere exatamente estas strings.
TAREFA_DOCUMENTO = "RETRIEVAL_DOCUMENT"
TAREFA_CONSULTA = "RETRIEVAL_QUERY"


class ChaveDeApiAusente(RuntimeError):
    """`GOOGLE_API_KEY` não está no ambiente.

    Tipo próprio pelo mesmo motivo de `BancoInacessivel`: a restauração passou
    a fazer chamada de rede (ADR-0020), e falhar **antes** de gravar qualquer
    coisa, com instrução, é melhor que estourar no meio dos 96 vetores.
    """


MENSAGEM_SEM_CHAVE = (
    "A restauração precisa gerar os vetores do regulamento, e isso exige a "
    "chave do Google AI Studio.\n"
    "\n"
    "Copie o exemplo e preencha a sua chave:\n"
    "    cp .env.example .env\n"
    "    # edite .env e preencha GOOGLE_API_KEY=...\n"
    "\n"
    "A chave sai de https://aistudio.google.com/apikey"
)


@runtime_checkable
class ClienteEmbedding(Protocol):
    """O que a restauração e a busca precisam de um modelo de embedding."""

    async def gerar_de_documentos(self, textos: list[str]) -> list[list[float]]:
        """Vetores dos trechos do regulamento. `RETRIEVAL_DOCUMENT`."""
        ...

    async def gerar_de_consulta(self, texto: str) -> list[float]:
        """Vetor de uma pergunta do morador. `RETRIEVAL_QUERY`."""
        ...


class EmbeddingGemini:
    """Implementação real, contra a API do Google AI Studio."""

    def __init__(
        self,
        *,
        chave: str | None = None,
        modelo: str = MODELO,
        dimensoes: int = DIMENSOES,
    ) -> None:
        """Monta o cliente. A chave vem da configuração, não do `os.environ`.

        ⚠️ **Não troque isto por `genai.Client()` sem chave explícita.** O SDK
        lê `GOOGLE_API_KEY` do `os.environ`, e o `.env` do projeto **não** é
        copiado para lá — então a chave do arquivo seria ignorada e o comando
        recusaria dizendo que não há chave. Foi o bug encontrado ao escrever
        este módulo; ver `app/config.py`.
        """
        if chave is None:
            from app.config import obter_configuracao

            # O `os.environ` entra como alternativa, não como fonte principal:
            # é o que faz `GOOGLE_API_KEY=... uv run ...` continuar
            # funcionando para quem preferir passar por variável.
            chave = obter_configuracao().google_api_key or os.getenv("GOOGLE_API_KEY", "")

        if not chave:
            raise ChaveDeApiAusente(MENSAGEM_SEM_CHAVE)

        from google import genai
        from google.genai import types

        # ⚠️ Timeout, pelo mesmo motivo de `app/agentes/modelo.py`: sem ele, um
        # socket pendurado espera para sempre e nenhuma retentativa dispara,
        # porque silêncio não é erro. 60 s pega socket morto sem apertar a
        # latência de uma chamada normal.
        self._cliente = genai.Client(
            api_key=chave,
            http_options=types.HttpOptions(timeout=60_000),
        )
        self._modelo = modelo
        self._dimensoes = dimensoes

    async def _gerar(self, textos: list[str], tarefa: str) -> list[list[float]]:
        from google.genai import types

        # Uma lista inteira numa chamada: o SDK a transforma em UMA requisição
        # a `:batchEmbedContents` (medido no spike 2.4, achado 9). Os 96
        # artigos custam 1 requisição contra 1.000/dia de quota — a
        # preocupação de estourar o limite por minuto não se sustenta.
        def chamar():
            return self._cliente.models.embed_content(
                model=self._modelo,
                contents=textos,
                config=types.EmbedContentConfig(
                    task_type=tarefa,
                    output_dimensionality=self._dimensoes,
                ),
            )

        # O SDK é síncrono; `to_thread` evita bloquear o loop de quem chama.
        resposta = await asyncio.to_thread(chamar)
        vetores = [list(e.values) for e in resposta.embeddings]

        if len(vetores) != len(textos):
            # ⚠️ Rede de segurança contra a armadilha `M-5`. O `-001` devolve
            # um vetor por item — medido —, mas se alguém trocar o modelo pelo
            # `-2` sem embrulhar cada trecho num `Content`, a resposta vira UM
            # vetor agregado, sem erro, e a busca passa a responder sempre a
            # mesma coisa. Aqui isso vira exceção em vez de 96 vetores iguais.
            raise RuntimeError(
                f"o modelo {self._modelo} devolveu {len(vetores)} vetores para "
                f"{len(textos)} textos. Se o modelo foi trocado, cada trecho "
                "precisa ir num `Content` próprio (restrição M-5, spike 2.4)."
            )
        return vetores

    async def gerar_de_documentos(self, textos: list[str]) -> list[list[float]]:
        return await self._gerar(textos, TAREFA_DOCUMENTO)

    async def gerar_de_consulta(self, texto: str) -> list[float]:
        return (await self._gerar([texto], TAREFA_CONSULTA))[0]
