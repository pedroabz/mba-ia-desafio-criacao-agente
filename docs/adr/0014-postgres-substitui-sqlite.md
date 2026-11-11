# ADR-0014 — Postgres com `pgvector` substitui o SQLite, para todo o armazenamento

**Status:** aceito
**Data:** 2026-11-08
**Origem:** decisão tomada na revisão do [spike 1.4](../spike-1.4-estrategia-regulamento.md), não em spike
**Invariantes e garantias afetados:** `I-01`, `I-03` (os índices migram); Garantia 3 (persistência de sessão)
**Relacionado:** ADR-0015 (a recuperação semântica que motivou a mudança) · **substitui a escolha de banco de** ADR-0002 e ADR-0006, que continuam válidos no resto

## Contexto

O Residencial Aurora guardava tudo em SQLite: as tabelas de domínio (apartamento, área, reserva, autorização de entrada) e, pela Garantia 3, a sessão de conversa do ADK.

A decisão de usar recuperação **semântica** para o regulamento (ADR-0015) introduz um novo tipo de dado: vetores de embedding. Guardá-los exige ou uma estrutura própria ao lado do SQLite, ou um banco que já saiba lidar com eles.

Isso trouxe a pergunta à tona: **se um Postgres com `pgvector` vai existir para os vetores, faz sentido manter o SQLite ao lado para o resto?** Operar dois bancos numa aplicação deste tamanho significa duas conexões, duas configurações de teste, dois lugares para o comando de restauração tocar e nenhuma transação atravessando os dois.

O enunciado do desafio antecipa explicitamente esse cenário: *"Armazenamento livre. Se ele depender de algum serviço externo, como um banco em container, esse serviço sobe com um comando documentado no README."*

## Decisão

**Um Postgres, com a extensão `pgvector`, para tudo**: tabelas de domínio, vetores do regulamento e sessões do ADK.

O serviço sobe por `docker compose`, com o comando documentado no README, como o enunciado exige. O SQLite sai do projeto.

Os dois índices que sustentam invariantes migram sem mudar de significado:

| Índice | Em Postgres |
|---|---|
| `UNIQUE (codigo)` sobre toda a tabela (`I-03`) | idêntico |
| `UNIQUE (area, data) WHERE ativa = 1` (`I-01`) | índice parcial — Postgres suporta nativamente |

## Alternativas consideradas

- **Manter SQLite e guardar os vetores nele**, como `BLOB`, com similaridade calculada em Python. São 14 vetores: o cálculo é trivial e não precisa de índice aproximado. Rejeitada porque resolve o armazenamento sem resolver a desproporção: continuaríamos com um banco que não sabe o que é um vetor, e com busca vetorial escrita à mão.
- **Dois bancos — Postgres só para os vetores, SQLite para o resto.** Evitaria mexer no que já funciona, inclusive na retomada de confirmação já verificada. Rejeitada pelo custo operacional permanente: dois serviços, duas configurações, duas fontes para o comando de restauração — para economizar uma migração que acontece uma vez.
- **Permanecer com recuperação léxica e sem Postgres.** Era o caminho recomendado pelo spike 1.4 e foi abandonado pelo que o ADR-0015 registra.

## Consequências

**O que fica mais fácil:** uma conexão, uma configuração, um lugar para restaurar. O índice parcial de `I-01` deixa de ser um recurso peculiar do SQLite e passa a ser uma construção comum. E a busca vetorial vem do banco, não de código nosso.

**O que fica mais difícil, ou passa a custar atenção:** o projeto passa a depender de um **serviço externo**. Subir a aplicação deixa de ser `uv run` e passa a exigir um container no ar. O passo 1 do roteiro do avaliador roda num clone limpo — se o `docker compose` falhar na máquina dele, nada funciona. O README precisa deixar isso explícito, e o comando de subida precisa falhar com mensagem clara quando o banco não estiver acessível.

Perde-se também a propriedade de os testes rodarem contra um arquivo temporário descartável. Os 16 cenários `@storage` hoje criam um SQLite por teste; com Postgres eles precisam de um banco de teste, com isolamento entre casos.

**Risco aceito — e é o que exige mais cuidado:** **a retomada da confirmação de ferramenta foi verificada com SQLite, não com Postgres.** O enunciado nomeia explicitamente o serviço de sessão como um dos fatores que alteraram esse comportamento nos testes do autor — *"essa escolha mudou conforme a topologia dos agentes, os bloqueios de transferência, a configuração de retomada do App e **o serviço de sessão**"* — e a falha é silenciosa: a rota aceita, nada dá erro, e a ação não executa.

Mitigação obrigatória: **verificar a retomada em Postgres antes de migrar qualquer outra coisa.** É o primeiro passo do plano, de propósito. Se falhar ali, descobre-se barato e a decisão é revista antes de haver trabalho jogado fora.

## Verificação

| Cenário | Protege | Tipo |
|---|---|---|
| A retomada da confirmação funciona com sessão em Postgres | o risco aceito acima | **regressão** — é o cenário que autoriza o resto da migração |
| Uma reserva ativa por área e data, no instante da gravação | `I-01` | **regressão** — falha se o índice parcial não migrar com a cláusula |
| Código de reserva nunca se repete, nem de cancelada | `I-03` | **regressão** |
| Os dados sobrevivem ao reinício da aplicação | Garantia 3 | **regressão** |
| Subir a aplicação sem o banco no ar falha com mensagem clara | a dependência de serviço externo | positivo |

Arquivos: `tests/features/persistencia.feature`, `tests/features/reservas.feature`

## Onde isso vive no código

| O quê | Onde |
|---|---|
| O serviço do banco | `compose.yaml` → `banco` (`pgvector/pgvector:pg17`, porta **5433** no host) |
| URL, fonte única | `app/config.py` → `Configuracao.url_banco` |
| DDL em Postgres e `CREATE EXTENSION vector` | `app/infra/banco.py` → `DDL`, `DDL_EXTENSAO` |
| Engine, com `search_path` e `NullPool` | `app/infra/banco.py` → `criar_engine` |
| Recusa legível quando o banco não responde | `app/infra/banco.py` → `BancoInacessivel`, `MENSAGEM_INACESSIVEL`, `_e_falha_de_conexao` |
| Saída limpa dos comandos | `app/cli.py` → `_sair_com_instrucao` |
| Repositório | `app/infra/repositorio_postgres.py` → `RepositorioPostgres` |
| Isolamento entre casos de teste | `tests/conftest.py` → `schema_teste`, e `app/infra/banco.py` → `remover_schema` |
| A prova da retomada, em dois processos | `tests/processo_retomada.py` |

**O risco aceito não se materializou, e isso foi medido antes de migrar.** O
`P1` do plano 1.4 rodou a retomada da confirmação com a sessão do ADK em
Postgres, em **dois processos separados**: a pendência nasce no processo A sem
gravar nada, o processo morre, e o processo B — que nunca viu aquele objeto de
sessão — aprova e a reserva é criada **exatamente uma vez**. Verificado por
sabotagem: trocar `DatabaseSessionService` por `InMemorySessionService`
derruba o cenário com `SessionNotFoundError`.

⚠️ **`NullPool` em `criar_engine` não é desleixo.** Uma conexão do `asyncpg`
fica presa ao event loop que a abriu, e os passos do `pytest-bdd` são
síncronos: cada um roda a sua corrotina num loop **novo**. Com pool, o segundo
passo de um cenário pega conexão de outro loop e morre com `got Future
attached to a different loop` — derrubou **29 cenários de uma vez** na
migração. Com SQLite o problema não existia.

⚠️ **A suíte agora exige Docker.** É a consequência operacional que este ADR
aceitou, e ela ficou concreta: sem `docker compose up -d --wait`, os cenários
`@storage` e `@api` falham. A mensagem de `BancoInacessivel` diz o comando.

**O que a troca não exigiu:** nenhuma linha de lógica do repositório. Ele
distingue as colisões possíveis **consultando o estado do banco** depois da
falha, não lendo mensagem de erro do driver — escolha que o ADR-0011 e a
Garantia 5 pediram por outro motivo e que tornou a migração portável de graça.

Verificado por 20 cenários `@storage` e `@api` em vários arquivos, mais
`A retomada da confirmação funciona com sessão em Postgres`,
`Subir a aplicação sem o banco no ar falha com mensagem clara` e
`A restauração sem o banco no ar falha com mensagem clara e sem rastro`,
todos verdes.
