# ADR-0002 — Apartamentos e áreas são semeados no SQLite a partir de `dados/`

**Status:** aceito
**Data:** 2026-11-08
**Origem:** [`docs/spike-1.1-dominio-invariantes.md`](../spike-1.1-dominio-invariantes.md) → `dominio/D-05`
**Invariantes e garantias afetados:** nenhum invariante próprio; habilita a integridade referencial de `reserva`
**Relacionado:** ADR-0003 (valida área contra a tabela que esta decisão cria)

## Contexto

O Residencial Aurora é um assistente de condomínio exposto por uma API. O repositório do desafio traz o estado inicial em arquivos JSON: `dados/apartamentos.json` (6 apartamentos, com o nome do morador) e `dados/areas.json` (3 áreas reserváveis, cada uma com sua taxa).

Esses dois conjuntos têm uma característica que os separa do resto do domínio: **nunca mudam**. O assistente só os consulta — não cria apartamento nem altera taxa de área. Reservas e autorizações de entrada, ao contrário, são criadas e removidas pela conversa e vivem em SQLite.

O enunciado exige que os arquivos de `dados/` fiquem **byte-idênticos** aos do repositório base, e o avaliador confere isso explicitamente (passo 15). Isso restringe o que se pode fazer com eles, mas não responde onde esses dados ficam acessíveis **em tempo de execução**, com o resto do domínio já num banco.

## Decisão

Apartamentos e áreas são **semeados em tabelas do SQLite** a partir de `dados/*.json`, no mesmo arquivo de banco onde vivem reservas e autorizações.

A tabela é a **única fonte de verdade em tempo de execução**. Os arquivos em `dados/` são a origem do seed e o que o avaliador inspeciona; nenhum código lê JSON durante uma conversa.

`reserva.apartamento` e `reserva.area` são chaves estrangeiras para essas tabelas.

## Alternativas consideradas

- **Carregar os JSON em memória no startup**, deixando no banco apenas reservas e visitantes. Era a recomendação original do spike e foi rejeitada por produzir **duas fontes de verdade para a mesma informação**: a validação de área consultaria estruturas em memória enquanto o resto do domínio consultaria o banco. Sem integridade referencial, uma reserva poderia apontar para área inexistente caso a validação na ferramenta falhasse.

## Consequências

**O que fica mais fácil:** existe um só lugar para perguntar "esta área existe?" e "qual a taxa dela?". A integridade de `reserva.area` e `reserva.apartamento` passa a ser imposta pelo banco, não por validação espalhada. A validação de área (ADR-0003) consulta a mesma tabela que a reserva referencia, sem possibilidade de divergirem.

**O que fica mais difícil, ou passa a custar atenção:** o seed vira pré-requisito de qualquer uso — banco sem seed é banco quebrado, não banco vazio. O comando de restauração precisa decidir explicitamente se re-semeia as tabelas de referência ou só reservas e visitantes. E passa a existir uma cópia dos dados que, em princípio, pode divergir da fonte que o avaliador inspeciona.

**Risco aceito:** a divergência entre a tabela e `dados/*.json`. Ela é aceitável porque só pode ocorrer por um seed malfeito — nenhuma ação do assistente altera essas tabelas, já que não existe operação que as escreva. É um erro verificável uma vez, na subida, e não um risco contínuo.

## Verificação

| Cenário | Protege | Tipo |
|---|---|---|
| Seed carrega os 6 apartamentos e as 3 áreas de `dados/` | a decisão deste ADR | positivo |
| Os arquivos em `dados/` permanecem byte-idênticos após subir e usar a API | exigência do passo 15 | **regressão** — falha se algum código escrever em `dados/` |

Arquivo: `tests/features/referencia.feature`

**Nota sobre cenário de regressão contra a alternativa rejeitada:** não existe observação pela API que distinga "áreas em memória" de "áreas no banco" — as duas respondem igual às mesmas perguntas. A diferença está em acoplamento e em número de fontes de verdade, que teste não alcança. Os dois cenários acima protegem a decisão por outro ângulo: que o seed funciona e que a fonte original não é corrompida.

## Onde isso vive no código

| O quê | Onde |
|---|---|
| Tabelas `apartamento` e `area` | `app/infra/banco.py` → `DDL`, 1º e 2º comandos |
| Chaves estrangeiras de `reserva` | `app/infra/banco.py` → `REFERENCES apartamento(numero)` / `area(id)` |
| Seed a partir de `dados/*.json` | `app/infra/seed.py` → `semear` |
| Leitura da referência | `app/infra/repositorio_postgres.py` → `listar_areas`, `buscar_area` |
| Comando de restauração | `app/cli.py` → `restaurar` (`uv run aurora-restaurar`) |
| URL do banco, fonte única | `app/config.py` → `Configuracao.url_banco` |

⚠️ **O banco mudou depois que este ADR foi aceito.** A decisão continua
valendo inteira — apartamentos e áreas são semeados de `dados/` numa tabela,
que é a fonte de verdade em tempo de execução — mas o banco agora é **Postgres**
(ADR-0014), e três ponteiros desta seção mudaram com ele:

- a linha do `PRAGMA foreign_keys = ON` **saiu**, e isso é ganho: ela existia
  porque o SQLite desliga a checagem por conexão, e sem ela as `REFERENCES`
  eram decoração. O Postgres sempre impõe. O cenário que pegava isso continua
  verde, agora cobrando que a `REFERENCES` esteja escrita;
- `repositorio_sqlite.py` virou `repositorio_postgres.py`;
- `Configuracao.caminho_banco` virou `Configuracao.url_banco`.

O título deste arquivo diz "no SQLite" e foi mantido: renomeá-lo apagaria o
registro de que a decisão foi tomada quando o armazenamento era outro.

Verificado por 3 cenários em `tests/features/referencia.feature` e 2 em `tests/features/persistencia.feature`, todos verdes.
