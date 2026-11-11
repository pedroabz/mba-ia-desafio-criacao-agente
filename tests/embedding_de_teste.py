"""Cliente de embedding falso, para semear sem chave de API.

Existe porque os cenários do seed do regulamento são `@storage`, e `@storage`
significa *"não precisa de modelo"*. O que eles cobram — que haja um trecho
por artigo, que cada vetor tenha 768 dimensões, que nenhum vetor seja igual ao
de outro, e que o `task_type` seja o certo em cada sentido — não depende de o
vetor ser semanticamente bom. Depende de haver um vetor por trecho, com a
dimensão certa, gerado pela chamada certa.

O vetor é **derivado do texto por hash**: determinístico (a mesma suíte dá o
mesmo resultado duas vezes) e distinto por trecho (dois artigos diferentes
nunca colidem). Isso é o que torna verificável a asserção
*"nenhum vetor gravado é idêntico ao de outro trecho"* — que é a armadilha
`M-5` em forma de teste, e falharia se alguém trocasse o modelo por um que
agrega a lista num vetor só.
"""

from __future__ import annotations

import hashlib
import struct

from app.infra.embeddings import DIMENSOES, TAREFA_CONSULTA, TAREFA_DOCUMENTO


class EmbeddingDeTeste:
    """Implementa `ClienteEmbedding` sem rede. Registra o que foi pedido."""

    def __init__(self, *, dimensoes: int = DIMENSOES) -> None:
        self.dimensoes = dimensoes
        self.chamadas: list[tuple[str, int]] = []
        """`(task_type, quantidade_de_textos)` de cada chamada, em ordem."""

    def _vetor(self, texto: str) -> list[float]:
        """Deriva um vetor determinístico e único do texto, por hash."""
        numeros: list[float] = []
        contador = 0
        while len(numeros) < self.dimensoes:
            digest = hashlib.sha256(f"{texto}#{contador}".encode()).digest()
            # 8 floats por digest de 32 bytes.
            numeros.extend(struct.unpack(">8f", digest))
            contador += 1
        # Valores finitos e numa faixa sã: um `inf` vindo do unpack faria o
        # Postgres recusar a gravação, e o teste acusaria a coisa errada.
        return [max(-1.0, min(1.0, float(n) % 2 - 1)) for n in numeros[: self.dimensoes]]

    async def gerar_de_documentos(self, textos: list[str]) -> list[list[float]]:
        self.chamadas.append((TAREFA_DOCUMENTO, len(textos)))
        return [self._vetor(t) for t in textos]

    async def gerar_de_consulta(self, texto: str) -> list[float]:
        self.chamadas.append((TAREFA_CONSULTA, 1))
        return self._vetor(texto)

    # -- consultas que os `Então` fazem ------------------------------------

    def tarefas_usadas(self) -> list[str]:
        return [tarefa for tarefa, _ in self.chamadas]
