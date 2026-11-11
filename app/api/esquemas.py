"""Modelos Pydantic de request e response — o contrato da API, ao pé da letra.

Cada classe aqui espelha um bloco da seção "Contrato da API" do enunciado.
Nomes de campo, formatos e a *ausência* de campos são intencionais: a correção
é feita pelo contrato.

Datas usam `datetime.date`, que o Pydantic serializa como AAAA-MM-DD — o
formato exigido nas rotas de verificação.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# POST /sessoes
# ---------------------------------------------------------------------------


class CriarSessaoRequisicao(BaseModel):
    """`{"apartamento": "101"}`"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    apartamento: str = Field(min_length=1, examples=["101"])


class CriarSessaoResposta(BaseModel):
    """`201 {"session_id": "..."}`"""

    session_id: str


# ---------------------------------------------------------------------------
# POST /sessoes/{session_id}/mensagens
# POST /sessoes/{session_id}/confirmacoes
# ---------------------------------------------------------------------------


class EnviarMensagemRequisicao(BaseModel):
    """`{"texto": "Quero reservar o salão de festas para 2030-04-20"}`"""

    model_config = ConfigDict(extra="forbid")

    texto: str = Field(min_length=1, examples=["Reserve a quadra para 2030-04-06."])


class ResponderConfirmacaoRequisicao(BaseModel):
    """`{"id": "...", "confirmado": true}`"""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    confirmado: bool


class ConfirmacaoPendenteResposta(BaseModel):
    """Um item de `confirmacoes_pendentes`.

    O conteúdo de `acao` e os nomes dentro de `detalhes` são livres pelo
    enunciado; `detalhes` precisa trazer área+data (reserva) ou nome+data
    (visitante), o que é responsabilidade de quem monta a pendência.
    """

    id: str
    acao: str
    detalhes: dict[str, Any] = Field(default_factory=dict)


class ConversaResposta(BaseModel):
    """Formato de resposta das rotas de mensagens e de confirmações.

    `resposta` pode vir como string vazia quando a execução parou esperando
    confirmação. `confirmacoes_pendentes` lista todas as confirmações pendentes
    da sessão no momento da resposta, e é lista vazia quando não há nenhuma.
    """

    resposta: str = ""
    confirmacoes_pendentes: list[ConfirmacaoPendenteResposta] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# GET /sessoes/{session_id}/eventos
# ---------------------------------------------------------------------------


class EventoResposta(BaseModel):
    """Um evento da sessão, com o conteúdo completo.

    `conteudo` é um dicionário livre, de passagem: quando a Fase 2 trocar o
    serviço de sessão pelo do ADK, o `Event` serializado do ADK entra aqui
    inteiro, sem alterar o formato desta resposta.
    """

    id: str
    autor: str
    timestamp: datetime
    conteudo: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# GET /apartamentos/{numero}/reservas
# GET /apartamentos/{numero}/visitantes
# ---------------------------------------------------------------------------


class ReservaResposta(BaseModel):
    """`{"codigo": "RSV-1377", "area": "quadra", "data": "2030-03-09"}`

    ATENÇÃO: o contrato NÃO expõe `apartamento` aqui, apesar de o modelo de
    domínio ter esse campo. O número do apartamento já está no caminho da rota.
    """

    codigo: str
    area: str
    data: date


class VisitanteResposta(BaseModel):
    """`{"nome": "Marina Duarte", "data": "2030-03-16"}`"""

    nome: str
    data: date


# ---------------------------------------------------------------------------
# Erros
# ---------------------------------------------------------------------------


class ErroResposta(BaseModel):
    """Corpo de erro padrão do FastAPI (`{"detail": "..."}`)."""

    detail: str
