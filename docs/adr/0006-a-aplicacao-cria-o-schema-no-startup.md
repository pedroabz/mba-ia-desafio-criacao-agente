# ADR-0006 — A aplicação aplica o schema ao subir; a restauração só recarrega os dados

**Status:** aceito
**Data:** 2026-11-08
**Origem:** decisão tomada na revisão de [`docs/plano-1.1-persistencia.md`](../plano-1.1-persistencia.md), não em spike
**Invariantes e garantias afetados:** nenhum invariante; habilita a Garantia 3 (dados sobrevivem ao reinício)
**Relacionado:** ADR-0002 (define o que é semeado), ADR-0001 (define o schema das reservas)

## Contexto

O Residencial Aurora é um assistente de condomínio exposto por uma API FastAPI, com os dados em SQLite. O enunciado do desafio exige dois comandos documentados: um que **restaura** reservas e visitantes ao estado inicial dos arquivos em `dados/`, e outro que **sobe** a API em `http://localhost:8000`. O avaliador executa os dois, nessa ordem, num clone limpo do repositório (passo 1 do roteiro).

Isso deixou uma pergunta sem dono: num clone limpo não existe arquivo de banco nenhum — **quem cria o schema?** Nenhuma decisão anterior respondia, e as duas respostas plausíveis levam a estruturas de código diferentes.

A pergunta só apareceu porque um plano de implementação foi escrito e revisado antes de qualquer código: a primeira versão dele ligava a aplicação ao banco num passo e criava o schema num passo posterior, que declarava depender do primeiro. O passo que usava o banco vinha antes do que o criava.

## Decisão

**A aplicação aplica o schema ao subir**, chamando `aplicar_schema` na construção. O DDL é idempotente (`CREATE TABLE IF NOT EXISTS`, `CREATE UNIQUE INDEX IF NOT EXISTS`), então subir sobre um banco existente não altera nada.

**A restauração recarrega os dados** — apaga reservas e autorizações, regrava a referência e o estado inicial. Ela também aplica o schema, pela mesma idempotência, para funcionar num clone limpo sem depender de a API ter subido antes.

Em consequência: **subir a API funciona em qualquer máquina, sem passo prévio.**

## Alternativas consideradas

- **Só a restauração cria o schema; a aplicação assume que o banco existe** e falha com erro claro caso contrário. Dá um dono único à estrutura e garante que subir a API jamais altere o banco por efeito colateral. Rejeitada porque o custo cai todo em desenvolvimento: subir a API sem ter restaurado antes passa a dar erro, e isso acontece o tempo todo. No fluxo do avaliador a diferença não aparece — ele restaura antes de subir —, então a proteção extra não compra nada e a fricção é real.

## Consequências

**O que fica mais fácil:** subir a API nunca depende de um passo anterior ter sido executado. Um clone limpo, `uv sync` e o comando de subida bastam. Os testes também: cada um cria o schema no seu banco temporário sem orquestração.

**O que fica mais difícil, ou passa a custar atenção:** existem **dois pontos de entrada que criam estrutura** — a aplicação e a restauração. Enquanto o schema vier de um único `DDL` em `app/infra/banco.py`, eles não podem divergir; se algum dia alguém escrever DDL num dos dois lugares, divergem em silêncio. A regra que mantém os dois sãos é que nenhum deles define schema próprio: ambos chamam `aplicar_schema`.

**Risco aceito:** este projeto **não tem migração de schema**. A decisão vale enquanto isso for verdade. No dia em que o schema precisar evoluir sobre um banco com dados, `CREATE TABLE IF NOT EXISTS` deixa de ser suficiente — ele não altera tabela existente, e a aplicação subiria sobre um schema velho **sem reclamar**. Esse é o modo de falha silencioso desta escolha, e a saída seria introduzir versionamento de schema e mover a criação para um comando explícito, ou seja, voltar à alternativa rejeitada. Aceito porque o escopo do desafio não inclui evolução de schema.

## Verificação

| Cenário | Protege | Tipo |
|---|---|---|
| A aplicação sobe num diretório sem banco e cria o schema | a decisão deste ADR | positivo |
| A aplicação sobe sobre um banco já existente sem apagar dados | a idempotência do DDL | **regressão** — falha se a criação deixar de ser idempotente, ou se alguém "limpar antes de criar" |

Arquivo: `tests/features/persistencia.feature`

## Onde isso vive no código

| O quê | Onde |
|---|---|
| Aplicação do schema, idempotente e **síncrona** | `app/infra/banco.py` → `aplicar_schema` |
| Chamada ao subir a aplicação | `app/api/aplicacao.py` → `criar_app` |
| Chamada na restauração | `app/cli.py` → `restaurar` |
| DDL, fonte única dos dois caminhos | `app/infra/banco.py` → `DDL` |

⚠️ `aplicar_schema` continua **síncrona**, e a razão é a mesma de antes: criar
schema é operação estrutural de uma vez só, e exigir um event loop obrigaria
`criar_app()` a ser assíncrona ou a depender do `lifespan`, que **não dispara
em clientes ASGI de teste**.

O **como** mudou com o Postgres (ADR-0014). Antes era `sqlite3` da biblioteca
padrão, que é síncrono por natureza; o driver do Postgres é async-only, então
`aplicar_schema` roda a corrotina numa **thread com loop próprio**
(`app/infra/banco.py` → `_executar_sincrono`). Uma thread, e não
`asyncio.run` direto, para funcionar também se alguém a chamar de dentro de
código assíncrono — diferença que apareceria só nesse caso, e tarde.

E ela ganhou uma responsabilidade que o SQLite não tinha: **traduzir banco
inacessível em recusa legível** (`BancoInacessivel`), porque agora há um
serviço externo que pode não estar no ar. Dois cenários cobram isso.

A separação que sustenta este ADR: `app/infra/seed.py` → `semear` carrega
**apenas dados** e pressupõe o schema aplicado. Se algum dia o seed voltar a
criar estrutura, passam a existir duas definições de schema, que divergem em
silêncio.

Verificado por 2 cenários em `tests/features/persistencia.feature`, ambos verdes.
