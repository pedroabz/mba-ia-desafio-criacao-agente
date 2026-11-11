# Plano: migrar para Postgres com `pgvector` e preparar a recuperação semântica do regulamento

**Status:** executado em 2026-11-08
**Origem:** [ADR-0014](adr/0014-postgres-substitui-sqlite.md) e [ADR-0015](adr/0015-recuperacao-semantica-do-regulamento.md), decididos na revisão do [spike 1.4](spike-1.4-estrategia-regulamento.md). **Revisado em 2026-11-08**, na consolidação do [spike 2.4](spike-2.4-modelos-gemini.md): a decisão de embedding que travava o `P4` saiu, e os três critérios de pronto que apontavam para cenários inexistentes passaram a existir.
**Implementa:** ADR-0014, ADR-0015, [ADR-0020](adr/0020-embeddings-do-gemini-embedding-001-em-768-dimensoes.md), e **em parte** o [ADR-0016](adr/0016-recuperacao-por-artigo-devolvendo-lista.md) — só o fatiamento por artigo; a ferramenta de busca e a política de citação continuam fora

---

## O que este plano constrói

O **Residencial Aurora** é um assistente de condomínio exposto por uma API: o morador conversa por chat e reserva áreas comuns, cancela reservas, autoriza visitantes e tira dúvidas sobre o regulamento interno. Um avaliador corrige rodando 15 passos contra a API.

**Hoje o sistema guarda tudo em SQLite**, e isso funciona: existe um arquivo `aurora.db` criado ao subir a aplicação, com quatro tabelas, os índices que sustentam dois invariantes, e 20 cenários verdes sobre ele. A aplicação responde a partir desse banco e sobrevive a um reinício.

O que **não** existe ainda é qualquer coisa relacionada ao regulamento: nenhuma recuperação, nenhum vetor, nenhuma ferramenta.

Este plano faz duas coisas que foram decididas juntas e precisam acontecer juntas:

1. **Troca o SQLite por Postgres com `pgvector`**, para todo o armazenamento — domínio, sessão do ADK e os vetores que ainda virão. Uma aplicação, um banco.
2. **Deixa a recuperação semântica pronta para ser construída**: extensão habilitada, tabela de trechos com coluna de vetor, e os embeddings gerados e persistidos.

Quando terminar, a aplicação roda contra Postgres com o mesmo comportamento de hoje, o banco sobe por `docker compose` com comando documentado, e os vetores do regulamento estão gravados — faltando apenas a ferramenta que os consulta, que espera a **medição** dos cortes de similaridade. Medir exige os vetores existindo, e é este plano que os cria.

## O que fica de fora

| Não entra | Por quê |
|---|---|
| **A ferramenta `buscar_no_regulamento`** | **Não é mais falta de decisão** — a unidade é o artigo e a resposta é uma lista (ADR-0016). O que falta é **medição**: quantos artigos devolver e qual o corte de "não achei" foi decidido como *"a medir depois que os vetores existirem"* (`regulamento/D-08`), e são justamente estes passos que criam os vetores. Escrever a ferramenta antes seria fixar números no escuro. |
| **O especialista de Regulamento** | Depende da ferramenta acima. |
| **A política de citação na resposta** | Decidida no ADR-0016 (prosa curta citando o artigo; transcrição só sob pedido). Fica de fora porque vive **no especialista**, que não existe até a Fase 4. |
| **Os cenários `@recuperacao`** | Todos dependem da ferramenta. Seguem vermelhos. |
| **Afinar os limiares de corte** | Precisa dos vetores existindo *e* de medição. Este plano cria os vetores; medir vem depois. |

## O embedding: decidido, não mais pendente

Este plano nasceu com uma seção *"decisão pendente que este plano precisa antes de começar"* — **qual modelo gera os embeddings** —, e era ela que travava o `P4`. Ela foi **respondida** pelo [ADR-0020](adr/0020-embeddings-do-gemini-embedding-001-em-768-dimensoes.md), nascido da `modelos/D-04` do [spike 2.4](spike-2.4-modelos-gemini.md):

| | |
|---|---|
| **Modelo** | `gemini-embedding-001`, pela mesma chave do Google AI Studio que o projeto já exige |
| **Tipo de tarefa** | `task_type='RETRIEVAL_DOCUMENT'` ao semear · `task_type='RETRIEVAL_QUERY'` ao buscar |
| **Dimensão** | **768**, e a coluna é `vector(768)` — acima de 2.000 o `pgvector` não aceita índice `hnsw` nem `ivfflat` (`M-6`) |

O ADR traz o porquê, inclusive o custo que a escolha aceita (o modelo é depreciado, com desligamento em 2028-05-14) e o risco de troca futura (espaços de embedding são incompatíveis: mudar de modelo exige regerar todos os vetores). **Não há mais nada a decidir para o `P4` começar.**

## Passos

### P1 — Provar que a retomada da confirmação sobrevive em Postgres

**Implementa:** ADR-0014 (o risco aceito)
**Depende de:** —
**Entrega:** Postgres com `pgvector` subindo por `docker compose`; o harness do spike R1 (`scratchpad/spike_confirmacao.py`) rodando contra ele, em dois processos separados.

**Pronto quando:** fica verde `A retomada da confirmação funciona com sessão em Postgres`.

**Risco:** este é o passo que pode invalidar o plano inteiro. O enunciado nomeia o serviço de sessão como um dos fatores que mudaram esse comportamento nos testes do autor, e a falha é **silenciosa** — a rota aceita, nada dá erro, a ação não executa.

**Por isso ele é o primeiro.** Se falhar aqui, nada foi migrado ainda e a decisão do ADR-0014 volta à mesa com custo quase zero.

---

### P2 — O schema migra para Postgres

**Implementa:** ADR-0014
**Depende de:** P1
**Entrega:**
- `asyncpg` e `pgvector` no `pyproject.toml`
- `app/infra/banco.py` — DDL em Postgres, com `CREATE EXTENSION IF NOT EXISTS vector`
- os dois índices que sustentam invariantes: `UNIQUE (codigo)` e `UNIQUE (area, data) WHERE ativa = 1` (índice parcial, nativo em Postgres)
- `app/config.py` — URL do banco substituindo o caminho de arquivo
- `app/api/aplicacao.py` e `app/cli.py` apontando para a nova URL
- remoção do SQLite do projeto

**Pronto quando:** continuam verdes os 16 cenários `@storage` e os 4 `@api` que hoje passam, agora contra Postgres.

**Risco:** as fixtures de teste criam um SQLite temporário por teste. Com Postgres é preciso isolamento entre casos — transação revertida ao fim, ou schema por teste. Se isso não for resolvido, os testes passam a interferir uns nos outros e a suíte fica intermitente, que é pior que vermelha.

---

### P3 — Subida e restauração funcionam com o banco em container

**Implementa:** ADR-0014
**Depende de:** P2
**Entrega:**
- `compose.yaml` com Postgres + `pgvector`, volume nomeado e healthcheck
- `aurora-restaurar` e `aurora-servir` apontando para o container
- mensagem de erro clara quando o banco não estiver acessível
- comandos documentados, como o enunciado exige

**Pronto quando:** ficam verdes `A restauração devolve os dados ao estado inicial`, `A restauração não escreve em dados/` e `Subir a aplicação sem o banco no ar falha com mensagem clara`.

**Risco:** o passo 1 do roteiro do avaliador roda num **clone limpo**. Se o `docker compose` falhar na máquina dele, nada funciona — e o erro precisa dizer o que fazer, não empilhar rastro de pilha.

---

### P4 — Os artigos do regulamento viram vetores persistidos

**Implementa:** ADR-0015, ADR-0020, e o fatiamento do ADR-0016
**Depende de:** P3
**Entrega:**
- tabela `regulamento_trecho` com `capitulo`, `titulo`, `texto` e `embedding vector(768)` — a dimensão é do ADR-0020, não um parâmetro aberto
- fatiamento de `dados/regulamento.md` **por artigo**, com o título do capítulo embutido no texto antes de gerar o vetor (ADR-0016). São ~96 artigos
- geração dos embeddings com `gemini-embedding-001` e `task_type='RETRIEVAL_DOCUMENT'`, dentro do comando de restauração
- o lado da consulta já preparado para `task_type='RETRIEVAL_QUERY'` — a função que converte a pergunta em vetor, ainda sem a ferramenta que a chama
- índice vetorial, se o volume justificar. Para 96 artigos a varredura exata é instantânea; o que `vector(768)` preserva é a **opção** do índice, não desempenho hoje

**Pronto quando:** ficam verdes `O seed do regulamento grava um vetor para cada artigo` e `A coluna de vetor do regulamento tem 768 dimensões`.

**Risco:** a geração passa a fazer **chamadas de rede dentro de `aurora-restaurar`**, que antes era puramente local. No roteiro do avaliador isso funciona — o passo 1 preenche o `.env` **antes** de restaurar —, mas uma restauração sem chave precisa falhar dizendo isso, não estourar no meio da gravação. Custo medido no spike 2.4: os 96 vetores saem em **uma** requisição, porque o SDK transforma a lista numa única chamada a `:batchEmbedContents`.

> ⚠️ **O que este passo NÃO entrega, de propósito:** a ferramenta
> `buscar_no_regulamento`. Quantos artigos devolver e qual o corte de "não
> achei" foi decidido como **"a medir depois que os vetores existirem"**
> (`regulamento/D-08`, no ADR-0016) — e é este passo que os faz existir. A
> medição, e a ferramenta, vêm depois.
>
> **A granularidade não é mais uma dependência aberta.** O texto anterior deste
> passo citava `regulamento/D-01` como pendente; aquela decisão foi
> **substituída pela `D-07`, que está decidida** — unidade = artigo, com o
> título do capítulo embutido, e a recuperação devolvendo uma lista — e
> registrada no ADR-0016. O fatiador entra aqui, inteiro.

---

### P5 — Fechar o rastro

**Implementa:** —
**Depende de:** P1–P4
**Entrega:** seção *Onde isso vive no código* preenchida em ADR-0014, ADR-0015 e ADR-0020 (e, na parte do fatiador, no ADR-0016); ADR-0002 e ADR-0006 anotados com a mudança de banco; `CLAUDE.md` com os comandos novos.

**Pronto quando:** `uv run python scripts/cobertura.py` não acusa ponteiro quebrado.

**Risco:** —

## Cenários que este plano faz virar

Os quatro existem em `tests/features/` e estão `@pendente` hoje. **Três deles foram escritos na revisão deste plano**: os critérios de pronto de `P1`, `P3` e `P4` apontavam para nomes que não existiam em nenhum `.feature` — e passo cujo critério de pronto não é verificável não devia ter entrado no plano.

| Cenário | Passo | Arquivo |
|---|---|---|
| A retomada da confirmação funciona com sessão em Postgres | P1 | `persistencia.feature` |
| *(os 16 `@storage` e 4 `@api` que já passam)* | P2 | vários — **continuam verdes, não viram** |
| Subir a aplicação sem o banco no ar falha com mensagem clara | P3 | `persistencia.feature` |
| O seed do regulamento grava um vetor para cada artigo | P4 | `regulamento.feature` |
| A coluna de vetor do regulamento tem 768 dimensões | P4 | `regulamento.feature` |

**Continuam vermelhos**, e por quê:

| Cenário | Por quê | Destrava com |
|---|---|---|
| `Semear usa RETRIEVAL_DOCUMENT e buscar usa RETRIEVAL_QUERY` (ADR-0020) | o `P4` cobre o lado de semear; a metade da **busca** precisa de quem converte a pergunta em vetor dentro de uma consulta | a ferramenta `buscar_no_regulamento` |
| Os 5 `@recuperacao` de `regulamento.feature`, mais os 2 `Esquema do Cenário` sem etiqueta do mesmo arquivo | dependem da ferramenta de busca | a medição de `regulamento/D-08`, que o `P4` destrava |
| Os 3 `@conversa` de `regulamento.feature` | dependem do especialista de Regulamento | Fase 4 |
| Os 15 `@conversa` e 8 `@estrutura` dos outros arquivos | dependem dos agentes | Fase 4 |
| Os 3 `@api` de `modelos.feature` e os 3 de `guardrails.feature`, mais 1 de `ferramentas.feature` | dependem da rota de mensagens e da rota de confirmações | Fase 3.2 |

> A contagem acima é de 2026-11-08, depois da consolidação do spike 2.4, que
> acrescentou `modelos.feature`. Dois `Esquema do Cenário` de
> `regulamento.feature` estão **sem etiqueta nenhuma** — nem `@pendente`, nem
> camada; eles aparecem aqui porque existem e falham, mas a correção da
> etiqueta não é deste plano.

## Ordem e paralelismo

**Tudo sequencial, e o P1 é inegociável como primeiro.** Ele existe para descobrir barato: se a retomada quebrar em Postgres, o plano morre antes de haver trabalho migrado. Fazer P2 antes de P1 significaria migrar o schema inteiro para então descobrir que a sessão não funciona.

P4 pode ser adiado para um plano próprio sem prejuízo aos anteriores.

## Riscos do plano

- **O P1 pode reprovar a decisão do ADR-0014.** É o desenho: o passo existe para falhar cedo. Se falhar, a alternativa é voltar a SQLite para sessão e domínio, e usar Postgres só para vetores — que foi explicitamente rejeitado, mas por custo operacional, não por impossibilidade.
- **A migração dos testes para Postgres pode ser mais cara que a do código.** Isolamento entre casos é o ponto; subestimá-lo produz suíte intermitente.
- **Nenhuma decisão deste plano segue pendente** — era o risco que o rascunho anterior listava aqui, e ele saiu: a unidade de recuperação está no ADR-0016 e o modelo de embedding no ADR-0020. O que resta é **medição**, não escolha: os cortes de `regulamento/D-08` só se medem depois que os vetores existirem, e é o `P4` que os cria.
- **A decisão do ADR-0020 vale sobre números que não são nossos.** Ela não depende da quota (96 vetores em 1 requisição contra 1.000 por dia), mas depende de `gemini-embedding-001` continuar atendendo: ele é **depreciado**, com desligamento anunciado para 2028-05-14. Se o modelo sair do ar antes, os vetores precisam ser **regerados** com outro — os espaços de embedding são incompatíveis.

## Execução

| Passo | Estado | O que ficou verde |
|---|---|---|
| P1 | ✅ 2026-11-08 | `A retomada da confirmação funciona com sessão em Postgres` |
| P2 | ✅ 2026-11-08 | os 16 `@storage` e 4 `@api` seguem verdes, agora contra Postgres |
| P3 | ✅ 2026-11-08 | `Subir a aplicação sem o banco no ar falha com mensagem clara` + 1 cenário novo |
| P4 | ✅ 2026-11-08 | `O seed do regulamento grava um vetor para cada artigo`, `A coluna de vetor do regulamento tem 768 dimensões`, e mais 2 |
| P5 | ✅ 2026-11-08 | `cobertura.py` sem nenhum ponteiro quebrado |

**P1, o que a medição disse.** Pendência criada no processo A (`adk-…`), **0
reservas** gravadas; processo B, novo, aprova pelo `FunctionResponse` autorado
por `"user"` (R5) → **1 reserva**. A sessão em Postgres **não** quebra a
retomada, e o risco aceito do ADR-0014 não se materializou.

Verificado por sabotagem: trocar `DatabaseSessionService` por
`InMemorySessionService` derruba o cenário com `SessionNotFoundError`. O teste
pega.

O harness do spike R1 que o passo citava **não existia mais** (vivia num
`scratchpad/` de outra sessão). Foi reconstruído como
`tests/processo_retomada.py`, que é código de teste versionado em vez de
rascunho descartável — e roda em dois subprocessos de verdade, porque
reconstruir objetos no mesmo processo não distingue um `dict` de módulo de uma
linha de banco.

### P2 — o que a migração custou de verdade

**O risco previsto se materializou, e um não previsto também.**

O isolamento entre casos, que o plano nomeou, foi resolvido com **um schema do
Postgres por teste**, criado e derrubado pela fixture. Não foi transação
revertida porque `criar_app` monta o seu próprio engine, e um `ROLLBACK` de
fora não alcançaria o que ele gravou. Verificado: três rodadas seguidas, 20
verdes nas três, **zero schema deixado para trás**.

**O não previsto derrubou 29 cenários de uma vez:** uma conexão do `asyncpg`
fica presa ao event loop que a abriu, e os passos do pytest-bdd são síncronos
— cada um roda a sua corrotina num loop **novo**. Com pool, o segundo passo de
um cenário pega conexão de outro loop e morre com `got Future attached to a
different loop`. Com SQLite o problema não existia. A correção é `NullPool` no
engine: conexão nova por operação, o que ao volume deste projeto não custa
nada e elimina a classe inteira de acoplamento. Está comentado em
`app/infra/banco.py`, porque é exatamente o tipo de linha que alguém
"otimizaria" de volta.

**O que a troca deu de graça:** o `PRAGMA foreign_keys`, que o SQLite exigia
por conexão e sem o qual as `REFERENCES` eram decoração, desapareceu — o
Postgres sempre impõe. O índice parcial do `I-01`, que no SQLite era recurso a
conferir, é nativo.

**O que a troca não exigiu, e vale registrar:** nenhuma linha do repositório
mudou de lógica. Ele distingue as duas colisões possíveis **consultando o
estado do banco** depois da falha, não lendo mensagem de erro do driver — o
que o ADR-0011 e a Garantia 5 pediam por outro motivo, e que acabou tornando a
migração portável de graça.

Verificado por sabotagem: trocar o índice parcial por total derruba
**exatamente 1 cenário**, o de regressão do ADR-0001. A mesma precisão de
antes da migração.

**Vocabulário migrado.** Quatro cenários `@api` falavam de *arquivo* de banco,
que é palavra de SQLite. O que eles cobram — ADR-0006 idempotente, Garantia 3,
ler do banco e não da memória — não mudou; a redação passou a falar de
*schema*. Nenhum cenário foi apagado nem teve asserção enfraquecida.

### P3 — a mensagem certa no lugar errado

O `compose.yaml` e a `BancoInacessivel` já tinham nascido no P1 e no P2. O que
o P3 descobriu é que **ter a mensagem certa não basta**: o comando deixava a
exceção propagar, então o leitor via a instrução *depois* de vinte linhas de
rastro de pilha. E o passo 1 do roteiro do avaliador é alguém rodando
`uv run aurora-restaurar` num clone limpo.

`criar_app` e o **comando** são pontos de entrada diferentes e falhavam
diferente — o cenário que o plano previa cobria só o primeiro. O segundo
ganhou cenário próprio, que não estava no plano e passou a estar.

Verificado por sabotagem: tirar o `except` do CLI derruba o cenário novo.

### P4 — os 96 artigos, e dois bugs que ninguém tinha previsto

**A medição veio antes da gravação**, de propósito: descobrir que a dimensão
não é a esperada depois de gravar 96 vetores custaria regerar todos. As três
afirmações que estavam em *Não verificado* no spike 2.4 foram confirmadas
contra o servidor — 768 dimensões, N textos → N vetores distintos, `task_type`
aceito nos dois valores.

Depois: **96 artigos indexados em uma requisição, em menos de 5 segundos**, 96
vetores distintos, 14 capítulos.

**A medição que o `regulamento/D-08` esperava existe agora:**

| | melhor acerto |
|---|---|
| 6 perguntas dentro do escopo | 0,699 – 0,763 |
| 3 perguntas fora do escopo | 0,556 – 0,598 |

Folga de ~0,10 entre o pior acerto legítimo e o melhor falso positivo.
Inclusive o caso que derrubou a busca léxica no spike 1.4: *"pode levar
cachorro na quadra?"* recupera o **Art. 56, Capítulo VIII** — um capítulo que
a pergunta não menciona. **A escolha do corte segue pendente e não é deste
plano**; o insumo dela está no ADR-0015.

**O bug que vale mais que o passo.** Ligar a geração de embeddings foi a
primeira coisa do projeto a de fato precisar da chave de API — e descobriu que
**o `.env` nunca era carregado no `os.environ`**. O `google-genai` lê de lá, e
`app/config.py` afirmava **por escrito** que não precisava ler a chave "porque
o SDK a lê direto". Com uma chave válida no arquivo, `aurora-restaurar`
recusava dizendo que não havia chave — no passo 1 do roteiro, que é
literalmente *preencher o `.env` e restaurar*. Era invisível porque a mensagem
era **plausível**: quem a lesse conferiria o arquivo, veria a chave lá, e não
teria pista nenhuma do que fazer. Corrigido, com cenário de regressão
verificado por sabotagem.

### P5 — o rastro

`cobertura.py` não acusa **nenhum ponteiro quebrado**. A única reclamação é
`I-04 não tem cenário que o cubra`, que é da categoria *sem cobertura* (obra
em andamento, depende das decisões do spike R1), não *ponteiro quebrado* —
é a distinção que o script existe para fazer.

Cinco ADRs apontavam para `app/infra/repositorio_sqlite.py`, que deixou de
existir: 0001, 0003, 0004, 0005 e 0012. Caminhos corrigidos, e os sete
símbolos citados conferidos um a um no arquivo novo.

ADR-0002 e ADR-0006 ganharam anotação, **sem** alteração de decisão: o
primeiro perdeu a linha do `PRAGMA foreign_keys` (que existia só porque o
SQLite desliga a checagem por conexão — o Postgres sempre impõe), o segundo
registra que `aplicar_schema` segue síncrona mas agora roda numa thread com
loop próprio. O título do ADR-0002 continua dizendo "no SQLite": renomeá-lo
apagaria o registro de que a decisão foi tomada quando o armazenamento era
outro.

`CLAUDE.md`, `TODO.md` (seções 1.4 e 2.2, que ainda diziam "por capítulo" e
"SQLite") e `.env.example` atualizados. No `.env.example` o comentário repetia
a premissa falsa do bug do P4, e agora diz o contrário com o porquê.

## Conferência do conjunto declarado

| Cenário declarado | Passo | Virou? |
|---|---|---|
| A retomada da confirmação funciona com sessão em Postgres | P1 | ✅ |
| os 16 `@storage` e 4 `@api` que já passavam | P2 | ✅ seguem verdes, contra Postgres |
| Subir a aplicação sem o banco no ar falha com mensagem clara | P3 | ✅ |
| O seed do regulamento grava um vetor para cada artigo | P4 | ✅ |
| A coluna de vetor do regulamento tem 768 dimensões | P4 | ✅ |

**Nenhum cenário declarado ficou vermelho.**

**Um cenário que o plano previa manter vermelho ficou verde**, e vale dizer por
quê: `Semear usa RETRIEVAL_DOCUMENT e buscar usa RETRIEVAL_QUERY`. O plano
supôs que ele dependia da ferramenta `buscar_no_regulamento`. Não dependia — a
capacidade de converter a pergunta com `RETRIEVAL_QUERY` **estava na entrega
declarada do P4**, e um cliente de embedding que registra o `task_type` a torna
observável sem ferramenta nenhuma. Foi erro de previsão do plano, não escopo a
mais.

**Dois cenários nasceram verdes e não estavam no plano**, cada um cobrindo um
bug real encontrado na execução:

| Cenário | Bug que ele trava |
|---|---|
| A restauração sem o banco no ar falha com mensagem clara e sem rastro | o comando empilhava rastro de pilha antes da instrução |
| A chave do .env chega a quem gera os embeddings | o `.env` nunca chegava ao `os.environ` |

**Estado da suíte:** 44 verdes (eram 37 antes deste plano), 49 `@pendente`
vermelhos de propósito, e **6 vermelhos que não são pendentes** — os dois
`Esquema do Cenário` de `regulamento.feature` **sem etiqueta nenhuma**, defeito
pré-existente já registrado e que não é deste plano.

`dados/` conferido byte-idêntico ao `HEAD`.

## Validação

- [x] Revisado e aprovado — 2026-11-08, por pedido explícito de execução.
