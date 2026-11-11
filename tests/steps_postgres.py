"""Passos dos cenários que dependem do Postgres (ADR-0014, plano 1.4).

O cenário central aqui é o `P1` do plano: **a retomada da confirmação funciona
com a sessão do ADK em Postgres?** Ele é o passo que podia invalidar o plano
inteiro, e por isso vem antes de qualquer migração.

Por que a implementação usa subprocesso em vez de só construir o runner duas
vezes: a falha que o cenário procura é "a pendência vivia na memória do
processo". Reconstruir objetos no mesmo processo não distingue um `dict` de
módulo de uma linha de banco. Dois processos distinguem.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from pytest_bdd import given, then, when
from sqlalchemy import text

from app.config import obter_configuracao
from app.infra.banco import BancoInacessivel

RAIZ = Path(__file__).resolve().parent.parent

COMO_SUBIR = (
    "O Postgres do projeto não está acessível. Suba-o com:\n"
    "    docker compose up -d --wait"
)


def _postgres_no_ar(url: str) -> bool:
    """Abre uma conexão e fecha. `True` se o banco respondeu."""
    import asyncio

    from sqlalchemy.ext.asyncio import create_async_engine

    async def tentar() -> bool:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conexao:
                await conexao.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
        finally:
            await engine.dispose()

    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(tentar())


def _rodar_fase(*argumentos: str) -> dict:
    """Roda uma fase do harness num processo próprio e devolve o JSON final."""
    processo = subprocess.run(
        [sys.executable, "-m", "tests.processo_retomada", *argumentos],
        cwd=RAIZ,
        capture_output=True,
        text=True,
    )
    assert processo.returncode == 0, (
        f"a fase {argumentos[0]!r} falhou (código {processo.returncode}).\n"
        f"stdout:\n{processo.stdout}\nstderr:\n{processo.stderr}"
    )
    ultima = [l for l in processo.stdout.strip().splitlines() if l.startswith("{")]
    assert ultima, f"a fase {argumentos[0]!r} não imprimiu JSON:\n{processo.stdout}"
    return json.loads(ultima[-1])


# ----------------------------------------------- P1 · retomada em Postgres


@given("a aplicação com a sessão do ADK em Postgres")
def _sessao_em_postgres(contexto, url_banco, schema_teste):
    assert _postgres_no_ar(url_banco), f"{COMO_SUBIR}\n(URL configurada: {url_banco})"
    contexto["url_banco"] = url_banco
    # Domínio e sessão no mesmo banco — "uma aplicação, um banco" (ADR-0014).
    # O domínio vai no schema deste teste; a sessão do ADK cria as tabelas
    # dela no `public`, porque é o `DatabaseSessionService` que as gerencia.
    contexto["schema"] = schema_teste


@given("uma confirmação pendente criada por outro processo")
def _pendencia_criada(contexto):
    resultado = _rodar_fase(
        "pendencia", contexto["url_banco"], contexto["schema"]
    )
    assert resultado["confirmacao_id"], (
        "nenhuma pendência de confirmação foi criada — sem ela o cenário não "
        "tem o que retomar. Verifique o portão (ADR-0013)."
    )
    # A Garantia 1 em ação: pedir não grava. Se isto falhar, a confirmação não
    # está segurando a ação e o resto do cenário é irrelevante.
    assert resultado["reservas_antes_de_aprovar"] == 0, (
        "a reserva foi gravada ANTES da aprovação: o portão não segurou."
    )
    contexto["pendencia"] = resultado


@when("o processo é reiniciado e o morador aprova pela rota de confirmações")
def _reinicia_e_aprova(contexto):
    pendencia = contexto["pendencia"]
    # Processo NOVO: o anterior já terminou quando `_rodar_fase` retornou.
    contexto["aprovacao"] = _rodar_fase(
        "aprovar",
        contexto["url_banco"],
        contexto["schema"],
        pendencia["session_id"],
        pendencia["confirmacao_id"],
    )


@given("nenhum Postgres acessível na URL configurada")
def _banco_fora_do_ar(contexto):
    # Porta alta sem ninguém escutando. Não paramos o container de propósito:
    # o teste tem que poder rodar junto com os outros, que precisam do banco.
    contexto["url_banco_forcada"] = (
        "postgresql+asyncpg://aurora:aurora@localhost:5999/aurora"
    )
    assert not _postgres_no_ar(contexto["url_banco_forcada"]), (
        "esperava a porta 5999 vazia, mas alguém respondeu nela — "
        "o cenário não provaria nada."
    )


@then("a subida falha")
def _subida_falhou(contexto):
    erro = contexto.get("erro_subida")
    assert erro is not None, (
        "a aplicação subiu sem banco. Ela precisa falhar na subida: subir e "
        "só quebrar na primeira requisição deixaria o avaliador achando que "
        "está tudo bem."
    )
    assert isinstance(erro, BancoInacessivel), (
        f"esperava BancoInacessivel, veio {type(erro).__name__}: {erro!r}. "
        "Um erro de driver cru é exatamente o que o ADR-0014 quer evitar."
    )


@then("a mensagem de erro diz qual comando sobe o banco")
def _mensagem_diz_o_comando(contexto):
    mensagem = str(contexto["erro_subida"])
    assert "docker compose up" in mensagem, (
        "a mensagem não diz como subir o banco. O passo 1 do roteiro roda num "
        f"clone limpo; esta mensagem é a única instrução que o leitor tem:\n{mensagem}"
    )


@then("a mensagem não contém rastro de pilha")
def _mensagem_sem_rastro(contexto):
    mensagem = str(contexto["erro_subida"])
    for marca in ("Traceback", "File \"", ".py\", line", "asyncpg.exceptions"):
        assert marca not in mensagem, (
            f"a mensagem traz {marca!r}, que é rastro de pilha vazando para "
            f"quem só precisa saber qual comando rodar:\n{mensagem}"
        )


@when("o comando de restauração é executado")
def _roda_restauracao(contexto):
    import os

    ambiente = dict(os.environ)
    # `url_banco` vira `URL_BANCO` por padrão no pydantic-settings — é assim
    # que se aponta o comando para outro banco sem editar código.
    ambiente["URL_BANCO"] = contexto["url_banco_forcada"]
    contexto["processo"] = subprocess.run(
        [sys.executable, "-c", "from app.cli import restaurar; restaurar()"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        env=ambiente,
    )


@then("o comando sai com código de erro")
def _comando_falhou(contexto):
    processo = contexto["processo"]
    assert processo.returncode != 0, (
        "o comando de restauração saiu com 0 sem banco nenhum. "
        "Quem automatizar a subida não teria como notar a falha."
    )


@then("a saída diz qual comando sobe o banco")
def _saida_diz_o_comando(contexto):
    saida = contexto["processo"].stdout + contexto["processo"].stderr
    assert "docker compose up" in saida, (
        f"a saída não diz como subir o banco:\n{saida}"
    )


@then("a saída não contém rastro de pilha")
def _saida_sem_rastro(contexto):
    saida = contexto["processo"].stdout + contexto["processo"].stderr
    for marca in ("Traceback", 'File "', "asyncpg.exceptions", "sqlalchemy.exc"):
        assert marca not in saida, (
            f"a saída traz {marca!r} — rastro de pilha antes da instrução é "
            f"exatamente o que o P3 existe para evitar:\n{saida}"
        )


@then("a reserva criada pelo processo seguinte é exatamente uma")
def _criada_uma_vez(contexto):
    aprovacao = contexto["aprovacao"]
    assert aprovacao["reservas_depois_de_aprovar"] == 1, (
        "esperava exatamente 1 reserva depois da aprovação, achei "
        f"{aprovacao['reservas_depois_de_aprovar']} ({aprovacao['codigos']}). "
        "Zero significa que a retomada não executou a ação — a falha "
        "silenciosa que o ADR-0014 nomeia como risco aceito."
    )
