"""Passos dos cenários de quota — ADR-0018 e ADR-0019.

**Nenhum destes cenários gasta quota de verdade.** Um servidor HTTP local finge
ser o endpoint do Gemini e responde `429`, contando as requisições. É o mesmo
truque do spike 2.4, e é o que permite exercitar o caminho de erro sem esgotar
a chave de alguém.

Dois cenários são `@runner` (passam pelo runner do ADK, sem chave) e três são
`@api` (vão por HTTP, porque o `503` e o cabeçalho só existem nessa camada).
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, then, when

DADOS = Path(__file__).resolve().parent.parent / "dados"

CORPO_DE_QUOTA = {
    "error": {
        "code": 429,
        "status": "RESOURCE_EXHAUSTED",
        "message": "Quota exceeded for quota metric 'Generate requests'",
        "details": [
            {
                "@type": "type.googleapis.com/google.rpc.RetryInfo",
                # ⚠️ O SDK IGNORA este campo. Medido no spike 2.4: três
                # tentativas em 0,17 s com `initial_delay` baixo, mesmo com o
                # servidor pedindo 25 s. Fica aqui porque é o que o Google
                # manda de verdade, e porque alguém vai procurar por ele.
                "retryDelay": "25s",
            }
        ],
    }
}

CORPO_DE_SUCESSO = {
    "candidates": [
        {
            "content": {"role": "model", "parts": [{"text": "Tudo bem por aqui."}]},
            "finishReason": "STOP",
        }
    ]
}


class _EndpointFalso(BaseHTTPRequestHandler):
    """Responde `429` nas primeiras `recusas_iniciais` chamadas."""

    recusas_iniciais = 10_000
    chamadas = 0

    def do_POST(self) -> None:  # noqa: N802 — nome exigido pelo BaseHTTPRequestHandler
        type(self).chamadas += 1
        tamanho = int(self.headers.get("content-length") or 0)
        self.rfile.read(tamanho)

        recusar = type(self).chamadas <= type(self).recusas_iniciais
        corpo = json.dumps(CORPO_DE_QUOTA if recusar else CORPO_DE_SUCESSO).encode()

        self.send_response(429 if recusar else 200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, *_args) -> None:
        """Silêncio: o servidor imprimiria uma linha por requisição."""


@pytest.fixture
def endpoint_falso():
    """Sobe o servidor numa porta livre e devolve o controle dele."""
    _EndpointFalso.chamadas = 0
    _EndpointFalso.recusas_iniciais = 10_000

    servidor = HTTPServer(("127.0.0.1", 0), _EndpointFalso)
    thread = threading.Thread(target=servidor.serve_forever, daemon=True)
    thread.start()
    try:
        yield servidor
    finally:
        servidor.shutdown()
        servidor.server_close()


def _modelo_apontado_para(servidor, contexto):
    """Um `Gemini` real, com `retry_options` de verdade, falando com o stub.

    O que está sob teste é a **configuração de retentativa** (ADR-0018), não o
    modelo. Por isso o objeto é o mesmo que a aplicação monta — só o `base_url`
    muda.
    """
    from google.adk.models.google_llm import Gemini

    from app.agentes.modelo import RETENTATIVAS
    from app.config import MODELO

    porta = servidor.server_address[1]
    contexto["retentativas"] = RETENTATIVAS
    return Gemini(
        model=MODELO,
        retry_options=RETENTATIVAS,
        client_kwargs={
            "api_key": "chave-de-teste",
            "http_options": {"base_url": f"http://127.0.0.1:{porta}"},
        },
    )


# ───────────────────────────────────────────────────────────────── Dado


@given("um modelo que recusa toda requisição com 429")
def _recusa_sempre(contexto, endpoint_falso, url_banco, schema_teste, banco):
    from app.api.aplicacao import criar_app
    from app.infra.seed import semear
    from tests.conftest import rodar

    _EndpointFalso.recusas_iniciais = 10_000
    rodar(semear(banco, DADOS))
    contexto["app"] = criar_app(
        url_banco=url_banco,
        schema=schema_teste,
        modelo=_modelo_apontado_para(endpoint_falso, contexto),
    )
    contexto["repo"] = contexto["app"].state.repositorio


@given("um modelo que recusa a primeira requisição com 429 e aceita a segunda")
def _recusa_uma_vez(contexto, endpoint_falso, url_banco, schema_teste, banco):
    _recusa_sempre(contexto, endpoint_falso, url_banco, schema_teste, banco)
    _EndpointFalso.recusas_iniciais = 1
    _EndpointFalso.chamadas = 0


# ───────────────────────────────────────────────────────────────── Quando


@when("o morador envia uma mensagem")
def _envia_mensagem(contexto):
    from fastapi.testclient import TestClient

    # Por HTTP, não pelo objeto `Conversa`: três dos cinco cenários cobram o
    # código de status, que só existe nesta camada. Os outros dois não se
    # importam com o caminho.
    with TestClient(contexto["app"], raise_server_exceptions=False) as cliente:
        criada = cliente.post("/sessoes", json={"apartamento": "101"})
        assert criada.status_code == 201, criada.text
        sessao = criada.json()["session_id"]
        contexto["sessao_http"] = sessao
        contexto["resposta_http"] = cliente.post(
            f"/sessoes/{sessao}/mensagens", json={"texto": "oi, tudo bem?"}
        )
        contexto["cliente_http"] = cliente
        contexto["eventos_http"] = cliente.get(f"/sessoes/{sessao}/eventos")


@when("eu consulto GET /sessoes/{id}/eventos")
def _consulta_eventos(contexto):
    # A consulta já foi feita no passo anterior, dentro do mesmo `with` — o
    # `TestClient` fora do context manager monta um loop por requisição, e o
    # engine do ADK não sobrevive a isso (ver `tests/steps_confirmacao.py`).
    assert contexto["eventos_http"].status_code == 200, contexto["eventos_http"].text


# ───────────────────────────────────────────────────────────────── Então


@then("ele recebe uma resposta normal")
def _resposta_normal(contexto):
    resposta = contexto["resposta_http"]
    assert resposta.status_code == 200, (
        f"um 429 transitório derrubou o turno: {resposta.status_code} "
        f"{resposta.text}. Sem `retry_options`, UMA recusa é fatal — medido."
    )


@then(parsers.parse("foram feitas {quantas:d} requisições ao endpoint do modelo"))
@then(parsers.parse("foram feitas duas requisições ao endpoint do modelo"))
def _contagem_de_requisicoes(contexto, quantas: int = 2):
    assert _EndpointFalso.chamadas >= quantas, (
        f"esperava ao menos {quantas} requisições ao modelo, houve "
        f"{_EndpointFalso.chamadas}. Com a configuração padrão do ADK seria 1: "
        "a política de tentativas é `stop_after_attempt(1)` quando "
        "`retry_options` é None (`_api_client.py:677-678`)."
    )


@then("foram feitas três requisições ao endpoint do modelo")
def _tres_requisicoes(contexto):
    _contagem_de_requisicoes(contexto, 3)


@then("a espera inicial configurada entre as tentativas é de ao menos 2 segundos")
def _espera_configurada(contexto):
    retentativas = contexto["retentativas"]
    assert (retentativas.initial_delay or 0) >= 2, (
        f"`initial_delay` é {retentativas.initial_delay}. O SDK IGNORA o "
        "`retryDelay` que o servidor manda, então a espera é escolha nossa — e "
        "espera curta transforma três tentativas em três recusas em sequência, "
        "que é mitigação de aparência."
    )


@then('a rota NÃO responde 200 com "resposta" vazia')
def _nunca_200_vazio(contexto):
    resposta = contexto["resposta_http"]
    if resposta.status_code != 200:
        return
    corpo = resposta.json()
    assert corpo.get("resposta"), (
        "a rota devolveu 200 com `resposta` vazia por falha de quota. Pelo "
        "contrato, resposta vazia significa 'parei esperando confirmação' — "
        "a falha de quota se disfarçou de pendência. É a restrição M-4."
    )


@then("nenhuma confirmação pendente é publicada nessa resposta")
def _sem_pendencia_publicada(contexto):
    resposta = contexto["resposta_http"]
    if resposta.status_code != 200:
        return
    assert not resposta.json().get("confirmacoes_pendentes"), (
        "a resposta de uma falha de quota publicou confirmação pendente"
    )


@then(parsers.parse("a rota responde {codigo:d}"))
def _rota_responde(contexto, codigo):
    resposta = contexto["resposta_http"]
    assert resposta.status_code == codigo, (
        f"esperava {codigo}, veio {resposta.status_code}: {resposta.text[:200]}"
    )


@then("a resposta traz o cabeçalho Retry-After")
def _tem_retry_after(contexto):
    cabecalhos = contexto["resposta_http"].headers
    assert "retry-after" in {chave.lower() for chave in cabecalhos}, (
        f"sem Retry-After. Cabeçalhos: {dict(cabecalhos)}"
    )


@then(parsers.parse('existe um evento com error_code "{codigo}"'))
def _evento_de_erro(contexto, codigo):
    eventos = contexto["eventos_http"].json()
    bruto = json.dumps(eventos)
    assert codigo in bruto, (
        f"nenhum evento com error_code {codigo!r} na sessão. O Runner do ADK "
        "EMITE esse evento antes de levantar a exceção, e ele fica gravado — "
        "os passos 12 e 13 do avaliador contam os eventos da sessão."
    )
