# Plano: ligar a aplicação ao SQLite e expor os comandos de subida e restauração

**Status:** executado em 2026-11-08
**Origem:** triagem de [`docs/spike-1.1-dominio-invariantes.md`](spike-1.1-dominio-invariantes.md) (`consolidate-spike`)
**Implementa:** ADR-0001, ADR-0002 — a parte que ainda não chegou à aplicação

> **Documento histórico.** Este plano foi escrito e aprovado **antes** da
> implementação; o estado que ele descreve abaixo é o de 2026-11-08, antes dos
> passos serem executados. Mantido como está de propósito — reescrevê-lo no
> passado apagaria a informação de o que se sabia no momento de aprovar.

---

## O que este plano constrói

O **Residencial Aurora** é um assistente de condomínio exposto por uma API: o morador conversa por chat e reserva áreas comuns, cancela reservas e autoriza visitantes. O desafio é corrigido por um avaliador que roda 15 passos contra a API e confere os efeitos.

**Hoje não existe banco de dados algum neste projeto.** Não há arquivo `.db`, e a aplicação não fala com SQLite em momento nenhum: `criar_app()` constrói `RepositorioEmMemoria`, e tudo que a API grava morre quando o processo termina.

O que existe é o **código capaz de criar e usar esse banco**, escrito e testado mas nunca executado fora de teste:

| Arquivo | O que faz | Onde roda hoje |
|---|---|---|
| `app/infra/banco.py` | schema, com os índices que garantem exclusividade de reserva e unicidade perpétua do código | só em teste |
| `app/infra/repositorio_sqlite.py` | implementa a interface do repositório | só em teste |
| `app/infra/seed.py` | carrega `dados/*.json` para o banco | só em teste |

Os 14 cenários `@storage` que passam exercitam esse código contra um SQLite **temporário**, criado e descartado a cada teste. Eles provam que o código funciona; não provam que existe um banco, porque não existe.

Este plano transforma esse código em sistema, e entrega duas coisas que o enunciado exige:

- a **Garantia 3** ("nada se perde no reinício") passa a valer para os dados do condomínio — o passo 13 do avaliador reinicia a API sem restaurar e confere que reservas, cancelamentos e visitantes continuam valendo;
- os **comandos de subida e de restauração**, que o passo 1 do avaliador executa num clone limpo antes de qualquer outra coisa.

Quando este plano terminar, a API responde a partir do banco e sobrevive a um `Ctrl+C`.

## O que fica de fora

| Não entra | Por quê |
|---|---|
| **Persistência da sessão de conversa** | A outra metade da Garantia 3. Depende do `SessionService` do ADK, que só entra na Fase 4. Os dados do condomínio e a sessão são independentes: este plano resolve o primeiro. |
| **Se a restauração apaga as sessões** | O enunciado deixa explícito que é decisão nossa — e ela não pode ser tomada antes de sessões existirem. Volta como decisão pendente quando a Fase 4 começar. |
| **Organização das tabelas junto às do ADK** | Decisão `R1/D-05`, pendente. Não bloqueia: ela trata de o ADK compartilhar ou não o arquivo, e o ADK ainda não está ligado. Pode mudar como o engine é construído, não o schema nem o repositório. |
| **Os 6 cenários `@conversa`** | Dependem dos agentes (Fase 4) e de chave de API. Seguem vermelhos. |
| **Rotas `/mensagens` e `/confirmacoes`** | Fase 3.2, bloqueada pelas decisões pendentes do spike R1. |

## Decisão que destravou este plano

**Quem cria o schema do banco?** A pergunta não tinha dono: num clone limpo não existe arquivo de banco, e nenhum ADR dizia quem o cria. Ela só apareceu porque a primeira versão deste plano ligava a aplicação ao banco **antes** de qualquer passo criá-lo.

**Resolvida: a aplicação aplica o schema ao subir** — registrado em [ADR-0006](adr/0006-a-aplicacao-cria-o-schema-no-startup.md). A restauração recarrega os dados e também aplica o schema, pela idempotência do DDL. Consequência: subir a API funciona em qualquer máquina, sem passo prévio.

---

## Passos

### P1 — O banco passa a existir e a aplicação fala com ele

**Implementa:** ADR-0001, ADR-0002, ADR-0006
**Depende de:** —
**Entrega:**
- `app/config.py` — caminho do arquivo de banco, com padrão e sobrescrita por ambiente. **Um lugar só**: é daqui que a API e os comandos leem.
- `app/api/aplicacao.py` — `criar_app()` cria o engine, **aplica o schema** (`aplicar_schema`, idempotente) e constrói `RepositorioSQLite`
- remoção do uso de `RepositorioEmMemoria` na construção padrão
- o arquivo `.db` passa a existir de fato ao subir a aplicação

**Pronto quando:** ficam verdes
- `A aplicação sobe num diretório sem banco e cria o schema`
- `A aplicação sobe sobre um banco existente sem apagar dados`
- `As rotas de verificação leem do banco, não da memória`
- `O que foi gravado sobrevive ao reinício da aplicação`

**Risco:** o `lifespan` não dispara em clientes ASGI de teste — foi por isso que as seams entraram no `state` na construção, e não no ciclo de vida. O engine e a criação do schema precisam seguir a mesma regra, ou a app fica inutilizável em teste.

---

### P2 — Comandos de subida e de restauração

**Implementa:** ADR-0002
**Depende de:** P1 — ambos leem o caminho do banco do mesmo lugar
**Entrega:**
- um ponto de entrada de restauração que recarrega `dados/*.json` (e aplica o schema, por garantia — é idempotente)
- um comando de subida documentado, servindo em `http://localhost:8000`
- ambos registrados no `pyproject.toml` ou num `Makefile`, e documentados no README

**Pronto quando:** ficam verdes
- `A restauração devolve os dados ao estado inicial`
- `A restauração não escreve em dados/`

**Risco:** a restauração apaga reservas e autorizações. Se o caminho do banco divergir entre os dois comandos, ela apaga o banco errado — ou não apaga o certo, e o avaliador vê dados velhos. P1 fixar o caminho num lugar só é o que previne.

---

### P3 — Fechar o rastro nos ADRs

**Implementa:** —
**Depende de:** P1, P2
**Entrega:**
- seção *Onde isso vive no código* de ADR-0001 e ADR-0002 atualizada com os novos pontos
- `scripts/cobertura.py` rodando sem ponteiro quebrado

**Pronto quando:** `uv run python scripts/cobertura.py` não acusa ponteiro quebrado (os avisos de `I-04` e `I-05` seguem esperados — dependem da Fase 4)

**Risco:** —

## Ordem e paralelismo

Tudo sequencial, e por um motivo só: **P2 depende de P1 fixar o caminho do banco em um lugar.** Se os dois forem escritos em paralelo, cada um inventa o seu e a restauração passa a mirar um arquivo diferente do que a API serve — falha que não aparece em teste, porque cada teste usa um banco temporário próprio.

P3 é fechamento e só faz sentido depois dos dois.

## Riscos do plano

- **`R1/D-05` ainda pendente.** Se a decisão for "dois engines", o P1 muda — pouca coisa, e só na construção do engine. Avaliei que não justifica esperar: o schema e o repositório não mudam em nenhum dos cenários.
- **A Garantia 3 fica pela metade ao fim deste plano.** Os dados sobrevivem ao reinício; a sessão de conversa, não. O passo 13 do avaliador testa as duas coisas, e só passa inteiro depois da Fase 4. Está dito aqui para não parecer que a garantia foi fechada.

## Validação

- [x] Revisado e aprovado — 2026-11-08
- [x] Executado — 2026-11-08: P1, P2 e P3 concluídos, 6 cenários novos verdes
