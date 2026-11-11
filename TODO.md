# TODO — Assistente do Residencial Aurora

Plano de ataque do desafio.

> ✅ **Todas as fases fechadas, em 2026-11-09.**
> `99 cenários verdes · 0 @pendente · 0 decisão pendente · 22 ADRs`
> O roteiro do avaliador roda sozinho: `uv run python scripts/validar.py`
> (**59 verificações**). O que falta construir — nada — está em
> [`docs/planos/README.md`](docs/planos/README.md).

Legenda: 🔴 caminho crítico · 🟡 paralelizável · 🟢 independente

> **Este arquivo diz o que falta investigar e decidir.** O que falta **construir** — e o que já foi — está em [`docs/planos/README.md`](docs/planos/README.md).

> **Nota de reordenação.** A versão anterior deste plano colocava o spike da confirmação como Fase 0, antes da arquitetura. Estava errado: a arquitetura sai do **domínio e das garantias do enunciado**, não do mecanismo interno do ADK. O spike produz restrição de *ligação* (como amarrar um agente que confirma), não de *desenho* (qual agente existe). A evidência de que a ordem era invertida está no próprio spike: a decisão D-03 — quantos especialistas — saiu dele **não resolvida**, porque ele não tinha como resolvê-la.
>
> O spike já foi executado e seus achados continuam valendo. Ele agora vive em **Investigações de risco**, como entrada da Fase 1, não como precursor dela.

---

## Fase 1 — Arquitetura 🔴

> É aqui que o projeto é definido. Tudo abaixo decorre do enunciado: as 5 regras de negócio, as 5 garantias e o fluxo de 15 passos do avaliador. Nada aqui depende de detalhe interno do ADK.

### 1.1 Domínio, operações e invariantes ✅ INVESTIGADA — [`docs/spike-1.1-dominio-invariantes.md`](docs/spike-1.1-dominio-invariantes.md)
- [x] Entidades mapeadas, em **três categorias**: referência imutável (apartamento, área), mutável (reserva, autorização de visita) e não-entidade (regulamento, que é documento consultável).
- [x] Sete operações listadas e classificadas por escopo de leitura, escrita e confirmação. **Só `consultar_disponibilidade` lê fora do apartamento da sessão** — todas as outras são estritamente locais.
- [x] Invariantes escritos — **seis**, não cinco:

| # | Invariante | Imposto por |
|---|---|---|
| I-01 | Uma reserva ativa por `(area, data)` | **banco**, no instante da gravação |
| I-02 | Operação age só sobre o apartamento da sessão | **tool**, lendo `ToolContext.state` |
| I-03 | Código nunca repete, nem de cancelada | **storage** |
| I-04 | Cobrança/acesso só após confirmação | **`require_confirmation`** + rota de confirmações |
| I-05 | Regulamento nunca entra inteiro no contexto | **recorte da tool** |
| I-06 | Nenhum dado que identifique outro apartamento sai de uma tool | **projeção do retorno da tool** |

- [x] **I-06 é novo.** Estava embutido no I-02 e não deveria: `consultar_disponibilidade` precisa *ler* reserva alheia para responder, mas não pode *devolver* nada que identifique o dono (passo 10 proíbe `RSV-4821` e `302` isolado). Escopo e projeção são invariantes distintos.
- [x] Critério aplicado: **nenhum dos seis precisa depender do modelo** — cada um tem camada de código capaz de impô-lo. Nenhum está imposto hoje, o que é esperado nesta altura.
- [x] ⚠️ **I-06 é o único sem mecanismo que o force** (I-01 tem o banco, I-04 tem o ADK). Depende de o `return` da tool estar certo — quebra em silêncio. Candidato a teste dedicado na Fase 5.

**Achado que reduz risco:** o regulamento **não cria nenhuma regra** de reserva, taxa ou visitante (zero menções a taxa/valor/`R$`; Art. 36 e Art. 45 só apontam para o app). O especialista de Regulamento não tem como contradizer o Transacional sobre política.

**Achado que abre caso novo:** `areas.json` tem 3 áreas reserváveis, mas o Art. 4º, IV cita academia, brinquedoteca, playground — e há um capítulo inteiro sobre a piscina. "Reserve a piscina" é pedido plausível e não previsto pelo enunciado.

**6 decisões aguardando você:** `dominio/D-01` a `D-06` — visitante duplicado · área não reservável · identidade no cancelamento · cancelamento em lote · onde vivem apartamentos/áreas · unicidade perpétua do código. **Quatro são silêncios do enunciado**, não escolhas de implementação.

### 1.2 Fronteiras dos agentes ✅ INVESTIGADA — [`docs/spike-1.2-fronteiras-agentes.md`](docs/spike-1.2-fronteiras-agentes.md)

**Resolvido por medição, sem decisão a tomar:** `AgentTool` **isola** os eventos internos do especialista; `sub_agents` **não** (verificado: marcador presente num, ausente no outro; histórico de 7.493 vs 14.579 chars). Com a restrição `R1` — tool de confirmação não sobrevive em `AgentTool` —, cada especialista fica com o mecanismo que o outro **não pode** usar: Regulamento é `AgentTool` (isola contexto, Garantia 4), Transacional é `sub_agents` (preserva a confirmação, Garantia 1).

**✅ As 3 decisões foram tomadas e consolidadas** em ADR-0007, 0008 e 0009, com 10 cenários em `tests/features/agentes.feature` (todos `@pendente` — os agentes só existem na Fase 4).

| Agente | Acionamento | Determinado por |
|---|---|---|
| **Principal** | — | roteia; sem ferramenta que toque o banco; sem regulamento nas instruções |
| **Reservas** | `sub_agents`, `single_turn` | `F-1` — tem ferramenta que confirma |
| **Visitantes** | `sub_agents`, `single_turn` | `F-1` — tem ferramenta que confirma |
| **Regulamento** | `AgentTool` | `F-2` — consulta texto longo, não confirma |

> **Risco que a escolha de três especialistas ampliou** (registrado no ADR-0007): agora são **dois** agentes com ferramenta de confirmação, não um. A retomada roteia para o agente que pediu, e o spike R1 mediu isso com **um** só. Com dois, o roteador precisa acertar entre eles — não medido. Dois cenários de regressão cobrem (`A confirmação de reserva retoma no especialista de Reservas` e o par de Visitantes).

**Nenhum plano de implementação saiu daqui**, de propósito: nada está pronto para construir. Os agentes dependem da **1.3** (assinaturas das ferramentas) e da **1.4** (estratégia do regulamento), e os cenários `@conversa` dependem de `.env` com chave. O plano vem quando a 1.3 e a 1.4 fecharem.

**Migradas para cá:** `R1/D-01` e `R1/D-02` são decisões de fronteira, não de confirmação — aquele spike não tinha como respondê-las.

<details><summary>escopo original</summary>
- [ ] Derivar o número por **análise de fronteira**, não por meta. Para cada critério de corte candidato, aceitar ou **rejeitar com motivo escrito** (o README cobra o porquê).
- [ ] Fronteiras já levantadas na discussão:
  - **Regulamento** — forçada pela Garantia 4 (corpus próprio, proibido no contexto principal). Separado, não negociável.
  - **Transacional** (reservas + visitantes) — mesma amarração com o apartamento da sessão, mesma máquina de confirmação, mesmo storage.
  - *Rejeitado — corte por confirmação:* a taxa só é conhecida após consultar, então não dá para rotear antes.
  - *Rejeitado — corte leitura/escrita:* a consulta de disponibilidade precede imediatamente a gravação.
  - *Em aberto — corte por entidade* (Reservas | Visitantes): são 6 tools no total; dividir custa um hop a mais em chamadas ao modelo e em superfície de falha. → **D-03**.
- [ ] Agente principal: roteia, **sem tools de domínio** e **sem o regulamento nas instruções** (Garantia 4, passo 15).
- [ ] Registrar o motivo de cada escolha — é item avaliado.
</details>

### 1.3 Superfície de tools
- [ ] Fixar nomes e assinaturas. Proposta da discussão:
  - `consultar_disponibilidade(area, data)` → **apenas** `{livre: bool}`. Nunca o dono, nunca o código *(passo 10: a resposta não pode conter `RSV-4821` nem `302` isolado)*.
  - `listar_minhas_reservas()` → `[{codigo, area, data}]` do apartamento da sessão.
  - `criar_reserva(area, data)` → confirma **se `taxa > 0`** *(passo 6: quadra não confirma; passo 7: salão confirma)*.
  - `cancelar_reserva(area, data)` → **sem** confirmação, só do próprio apartamento *(passo 5)*. Por `area+data` e não por código, para o modelo nunca manipular código alheio *(passo 4)*.
  - `listar_meus_visitantes()` → `[{nome, data}]`.
  - `autorizar_visitante(nome, data)` → confirma **sempre** *(passo 11)*.
  - `buscar_no_regulamento(assunto)` → só o(s) capítulo(s) relevante(s).
- [ ] **Regra inegociável (Garantia 2):** nenhuma tool aceita `apartamento` escolhido pelo modelo. Vem do state da sessão via `ToolContext`. Se existir como parâmetro, precisa ser validado contra o da sessão e recusado se diferir. *(Conferido por leitura de código no passo 15.)*
- [ ] `detalhes` da pendência: área+data (reserva), nome+data (visitante). *(Passos 7 e 11.)*

### 1.4 Estratégia do regulamento (Garantia 4) ✅ INVESTIGADA E CONSTRUÍDA — [`docs/spike-1.4-estrategia-regulamento.md`](docs/spike-1.4-estrategia-regulamento.md)

> ⚠️ **Os três primeiros itens deste escopo foram REFUTADOS pela própria
> investigação**, e estão riscados em vez de apagados: eles registram uma
> hipótese que a medição derrubou, que é informação útil.

- [x] ~~Fatiar por **capítulo**~~ → **por ARTIGO** (ADR-0016). O spike mediu
      por que: a resposta a *"pode cachorro na quadra?"* está no Art. 56, do
      Cap. VIII, e o Cap. VI — que fala da quadra — não menciona animal
      nenhuma vez. Capítulo erraria, e devolver o capítulo inteiro violaria a
      Garantia 4. **96 artigos, 14 capítulos**, com o título do capítulo
      embutido no vetor.
- [x] ~~Busca por palavra-chave; embeddings provavelmente é exagero~~ →
      **busca semântica** (ADR-0015). `horas`, `horário`, `cachorro`,
      `barulho`, `gato` e `carro` têm **zero ocorrências** no regulamento: a
      busca léxica falhava em 86% das perguntas. Não era exagero, era o
      requisito.
- [x] Teste-alvo atingido: *"até que horas a piscina funciona aos domingos?"*
      recupera o **Art. 22 / Cap. IV** com 0,753 de similaridade. Medido
      contra os vetores reais.
- [x] ✅ **Destravado pela 1.2:** `AgentTool` **não** propaga os eventos
      internos para a sessão principal (medido). O especialista de Regulamento
      como `AgentTool` isola o texto consultado.
- [x] Consequência para o recorte, confirmada: o isolamento vem da topologia e
      **não** dispensa recuperar o trecho certo. Com 768 dimensões e cosseno,
      os 6 casos dentro do escopo acertam o capítulo certo em 0,699–0,763,
      contra 0,556–0,598 das perguntas fora de escopo.

**Construído pelo [plano 1.4](docs/plano-1.4-postgres-e-recuperacao-semantica.md),
executado em 2026-11-08.** O que **falta** é a ferramenta `buscar_no_regulamento`,
bloqueada por **uma decisão só**: `regulamento/D-08` — quantos artigos devolver
e qual o corte de "não achei". Era "a medir depois que os vetores existirem", e
os vetores agora existem; a medição está no ADR-0015.

### 1.6 Guardrails e resistência a injeção ✅ INVESTIGADA — [`docs/spike-1.6-guardrails.md`](docs/spike-1.6-guardrails.md)

> É a **tensão central declarada pelo enunciado**: *"o assistente não pode ser convencido a quebrar regra… se a regra mora só no prompt, uma mensagem bem escrita derruba a regra."* Olhar o sistema da perspectiva de quem ataca não é somar as defesas já registradas — é percorrer os ataques e perguntar, para cada um, **o que exatamente o impede**.

- [x] **8 dos 11 ataques morrem por ausência de capacidade.** Os três que o enunciado nomeia — fingir ser outro apartamento, afirmar ter confirmado, mandar ignorar instruções — falham porque **não existe ferramenta que faça o que eles pedem**. Prompt não é relevante para essas regras.
- [x] **3 frestas, e todas são a mesma:** dependem do `return` da ferramenta e da projeção da API.

| Fresta | Risco | Estado |
|---|---|---|
| `detalhes` da pendência repassa args crus | apartamento inventado pelo modelo chega à resposta → **reprova no passo 10** | depende de `superficie/D-04` ficar na Opção A |
| Retorno de `consultar_disponibilidade` | revela o dono da reserva (`I-06`) | depende do código da tool |
| Área não validada na consulta | "a piscina está livre" | 🐛 **bug confirmado em código já escrito** |

- [x] **Propriedade estrutural não planejada, que vale proteger:** nenhum texto livre de um morador atravessa a fronteira de outro apartamento. O único campo livre é o nome do visitante, lido de volta só pelo mesmo apartamento. **Injeção armazenada existe e não tem para onde ir** — e uma operação futura (listar visitantes de uma área comum, por exemplo) destruiria isso sem querer. Virou a restrição `G-4`.
- [x] 11 cenários de injeção escritos, **8 verificáveis sem chave de API** (testam ausência de capacidade).

**2 decisões aguardando você:** `guardrails/D-01` (texto suspeito em nome de visitante) · `D-02` (reagir ou ignorar tentativa de injeção).

**Sem decisão, mas vira trabalho:** corrigir `data_esta_livre`, que não valida a área. O ADR-0003 decidiu validar em runtime; foi implementado em `criar_reserva` e **esquecido** aqui.

---

> **A antiga 1.5 (mapa garantia → código) saiu da Fase 1.** Ela não era investigação: tinha um item só, sem alternativa a pesquisar nem decisão a tomar. E já está acontecendo — os 9 ADRs carregam `Invariantes e garantias afetados` e `Onde isso vive no código`, 6 deles já preenchidos com arquivo e símbolo. O mapa existe, distribuído; o que falta é **montá-lo**, e isso é trabalho da Fase 6. Movida para lá.

---

## Cenários BDD — a rede de proteção 🔴

> **Por que isto é uma seção e não um detalhe da Fase 5.** Os spikes produzem decisões cuja implementação vem semanas depois. Documento se lê uma vez e some na pasta; suíte de teste roda toda vez. Materializar o cenário **no momento em que a decisão é tomada**, vermelho e visível, é o que impede que a decisão se perca — por esquecimento, por troca de contexto, ou porque quem implementar depois (pessoa ou agente) não vai reler quatro documentos de spike.
>
> Regra que torna isso real: **cenário pendente nasce vermelho, nunca pulado.** `@skip` é invisível, e invisível é perdido.

### B.1 Esqueleto da suíte ✅ CONCLUÍDA
- [x] `pytest`, `pytest-bdd` 9.0.1 e `pytest-asyncio` no `pyproject.toml`; marcadores registrados.
- [x] `tests/features/` com os `.feature`, `tests/conftest.py` com fixtures e passos.
- [x] Gherkin em **português** confirmado (`Funcionalidade`, `Cenário`, `Dado`, `Quando`, `Então`, `Contexto`).
- [x] `pytest --collect-only` enxerga os 20 cenários.

> **Achado que simplificou tudo:** não foram necessários *stubs* de passo. Passo sem implementação já faz o cenário **falhar** com `StepDefinitionNotFoundError`, dizendo qual passo falta, em qual cenário e em qual linha — mais informativo que um `NotImplementedError` genérico, e sem código.

### B.2 Materializar os cenários ✅ CONCLUÍDA
- [x] `/generate-bdd` sobre a 1.1 → 20 cenários em 4 arquivos (`reservas`, `visitantes`, `referencia`, `sessao`).
- [ ] Rodar sobre [`docs/spike-R1-confirmacao-de-tools.md`](docs/spike-R1-confirmacao-de-tools.md) → cenários da Garantia 1. **Bloqueado:** as decisões daquele spike seguem pendentes.

### B.3 Ficar verde por camada
- [x] **`@storage` — 14 cenários, todos verdes.** Implementados junto com a Fase 2.3.
- [ ] `@conversa` — 6 cenários, **vermelhos**, esperando a Fase 4 e o `.env`.
- [ ] `@api` — nenhum ainda; virão com a 3.2.

> **A rede foi testada, não só escrita.** Sabotei o índice parcial de propósito (`WHERE ativa = 1` removido) e **exatamente 1 cenário falhou** — o de regressão do ADR-0001. Restaurado, 14 verdes. Cenário de regressão que não pega sabotagem é decorativo; este pega.

### B.4 Tornar a perda barulhenta ✅ CONCLUÍDA
- [x] `scripts/cobertura.py` — sai com código ≠ 0 e separa **ponteiro quebrado** (defeito) de **sem cobertura** (obra em andamento). Hoje acusa `I-04` e `I-05`, corretamente: dependem de fases que não rodaram.
- [x] `CLAUDE.md` na raiz, carregado por qualquer agente que abrir o projeto. Traz as regras inegociáveis e as armadilhas já pagas (`AgentTool` mata a confirmação, índice precisa ser parcial, `ativa = 1` em toda leitura, código alheio ≡ inexistente).

> **Limite honesto:** nada impede alguém de apagar os arquivos de teste. Mas aí a contagem da suíte muda e o `git diff` mostra. O objetivo não é tornar impossível — é tornar **barulhento**.

### B.5 Disciplina de asserção
- [ ] Nos `@conversa`, **verificar efeito, não prosa.** Comparar texto que o modelo escreveu quebra quando ele reformula, e teste ruidoso acaba desligado. Verificar: estado do banco depois, qual tool foi chamada com quais argumentos (está nos eventos da sessão), ausência de string proibida (`RSV-4821`, `302` isolado), presença ou não de confirmação pendente.
- [ ] O próprio enunciado trabalha assim: *"o texto das respostas só é conferido onde o passo diz"*.

---

## Fase 2 — Fundação 🟡

### 2.1 Setup do projeto ✅ CONCLUÍDA
- [x] `uv` + `pyproject.toml` + `uv.lock` versionados. Python **3.13**, `requires-python = ">=3.12"`.
- [x] ADK fixado: **`google-adk[db]==2.14.0`** (o extra `[db]` entrou depois; `sqlalchemy` não vem no core).
- [x] `.env.example` sem valores: `GOOGLE_API_KEY`, `GOOGLE_GENAI_USE_ENTERPRISE`. Nenhum `.env` criado.
- [x] `dados/` byte-idêntico ao `HEAD`.
- [x] Pacotes vazios: `app/`, `app/api/`, `app/dominio/`, `app/agentes/`.

> **📌 Variável de ambiente:** o genai lê `GOOGLE_GENAI_USE_ENTERPRISE` **e** `GOOGLE_GENAI_USE_VERTEXAI` (`google/genai/_api_client.py:871-890`); em conflito, `USE_ENTERPRISE` vence. O curso provavelmente ensinou o nome antigo — ambos funcionam.

### 2.2 Armazenamento — ✅ DECIDIDO, e a decisão MUDOU

- [x] ~~**SQLite**, sem serviço externo~~ → **Postgres com `pgvector`**
      (ADR-0014), em container. A troca veio da 1.4: a busca semântica precisa
      de vetores, e manter dois bancos para isso era economia burra. URL
      obrigatoriamente **`postgresql+asyncpg://`** — driver síncrono continua
      sendo rejeitado pelo `DatabaseSessionService`.
- [x] Sessão do ADK e dados de negócio no **mesmo banco**, em tabelas
      separadas. Segue valendo; o que mudou é que agora os vetores estão lá
      também. Uma aplicação, um banco.
- [x] **D-05 fechada pelos fatos:** um engine só, criado por
      `app/infra/banco.py` → `criar_engine`. O `DatabaseSessionService` cria e
      gerencia as tabelas dele (`sessions`, `events`, `app_states`,
      `user_states`, `adk_internal_metadata`), e as nossas quatro convivem no
      mesmo schema sem prefixo nenhum — verificado no banco.
- [x] **Custo operacional que a troca trouxe:** a suíte passou a exigir Docker.
      É a consequência que o ADR-0014 aceitou explicitamente.

### 2.3 Schema que sustenta as garantias ✅ CONCLUÍDA
- [x] **`app/infra/banco.py`** — schema com os dois índices de escopos diferentes: `UNIQUE(codigo)` sobre a tabela inteira (I-03) e `UNIQUE(area, data) WHERE ativa = 1` só sobre as ativas (I-01). Mais `PRAGMA foreign_keys = ON` por conexão, sem o qual as `REFERENCES` viram decoração.
- [x] **`app/infra/repositorio_sqlite.py`** — implementa a interface que já existia desde a 3.1; nenhuma rota precisou mudar. Grava e traduz `IntegrityError` em recusa de negócio, **nunca consulta antes para evitar o erro** — é o que a Garantia 5 exige.
- [x] **`app/dominio/erros.py`** — recusas de negócio. A distinção que importa: `AreaIndisponivel` (outro apartamento, **sem** dizer quem) vs `JaReservadaPorVoce` (o próprio, pode identificar).
- [x] **`app/infra/seed.py`** — carrega `dados/` para o banco; é também a restauração.
- [x] **Critério de pronto atingido:** os 14 cenários `@storage` passam. Não foi "o código roda" — foi a suíte ficar verde.

> **Bug meu, que vale registrar:** o DDL começou como um script único separado por `;`, com `split(";")`. Um comentário continha `ativa = 0; a linha PERMANECE` — e o ponto e vírgula dentro do comentário partiu o comando ao meio. Virou lista explícita de comandos: o `sqlite3` executa um por chamada mesmo, e parsing caseiro de SQL só espera a primeira string com `;` dentro.

- [x] **[`docs/plano-1.1-persistencia.md`](docs/plano-1.1-persistencia.md) — executado em 2026-11-08.** P1: `criar_app()` cria o banco, aplica o schema e constrói `RepositorioSQLite`. P2: `uv run aurora-restaurar` e `uv run aurora-servir`. P3: ponteiros de código nos ADRs 0001, 0002 e 0006.
- [x] **O banco existe de fato.** Testado ponta a ponta como o avaliador faria: clone sem `.db` → `aurora-restaurar` → `aurora-servir` → `GET /apartamentos/101/reservas` devolve `RSV-1377` e `/302/visitantes` devolve Marina Duarte. É o passo 1 do roteiro, passando.
- [x] **ADR-0006** nasceu aqui: ninguém tinha decidido quem cria o schema, e a primeira versão do plano ligava a aplicação ao banco **antes** de qualquer passo criá-lo. O gate de validação pegou.

### 2.4 Modelos Gemini ✅ INVESTIGADA — [`docs/spike-2.4-modelos-gemini.md`](docs/spike-2.4-modelos-gemini.md)

**O achado que inverte a intuição:** o plano gratuito dá **20 requisições por
dia** nos modelos da família Flash, contadas por projeto **e por modelo**. Um
turno de conversa custa **4 chamadas ao modelo** (medido: principal 2 +
especialista 2; +1 por ferramenta extra no mesmo turno), e o roteiro do
avaliador tem ~18 requisições que invocam o modelo → **70 a 85 chamadas**. Com
qualquer Flash, a correção morre por volta do passo 5. Os **Flash-Lite** dão
500/dia. O modelo "melhor" é o que reprova.

- [x] Modelos e limites conferidos — **com um bloqueio honesto:** o Google
      **parou de publicar** os limites do plano gratuito; a página oficial manda
      olhar *"View your active rate limits in AI Studio"*, que é autenticado e
      é do projeto **do avaliador**. Os números vêm de duas medições
      independentes de terceiros, que concordam. A doc também mudou de
      endereço: `ai.google.dev/gemini-api/docs` → `aistudio.google.com/docs`.
- [x] ⚠️ **`gemini-2.5-flash`, o do curso, tem desligamento em 2026-12-01**
      (roteia para `gemini-3.5-flash-lite`); `gemini-2.0-flash` já foi desligado.
- [x] ⚠️ **O padrão do ADK é um Flash.** `LlmAgent.DEFAULT_MODEL` é
      `gemini-3.5-flash`, que roteia para `gemini-3.8-flash` — o balde de
      20/dia. Agente sem `model=` cai nele **sem aviso nenhum**.
- [x] **O ADK não tenta de novo depois de um `429`** (medido: 1 requisição,
      exceção). `retry_options` resolve, e **ignora** o `retryDelay` que o
      servidor manda. `FallbackModel` troca de modelo no `429` (medido, com
      controle) — e como a quota é por modelo, é um balde novo.
- [x] **"Estourar quota vira 500" estava incompleto:** vira 500 **ou** `200`
      com `resposta` vazia, dependendo de como a rota consome os eventos. E
      `resposta` vazia é, pelo contrato, o sinal de *confirmação pendente* — uma
      falha de quota se disfarçaria de pendência. Virou a restrição `M-4`.
- [x] *Nota confirmada por execução:* `litellm` não está instalado e
      `gemini-*` resolve direto para a classe nativa `Gemini`. **Mas** qualquer
      `gemini-*` inventado é aceito na construção e só quebra na primeira
      chamada, com `404` — erro de digitação não falha ao subir (`M-7`).

**7 restrições derivadas** (`M-1` a `M-7`). `M-1` + `M-3` eliminam metade do
espaço de design antes de qualquer decisão: nada de Flash, e não se pode contar
com tier pago — **a chave é do avaliador**, preenchida por ele no passo 1.

**4 decisões tomadas e consolidadas em 2026-11-08.** `D-01` a `D-04` viraram
ADR, e os cenários que as protegem estão em `tests/features/`:

- [x] **`modelos/D-01` = A** — `gemini-3.5-flash-lite` nos **quatro** agentes,
      um balde só de 500/dia. [ADR-0017](docs/adr/0017-um-modelo-flash-lite-nos-quatro-agentes.md).
      ⚠️ Segue dependendo de item **não verificado**: 20/dia e 500/dia vêm de
      dois terceiros que concordam, não do Google.
- [x] **`D-02` = B** — `retry_options=HttpRetryOptions(attempts=3, initial_delay=2)`
      em cada modelo; **sem** `FallbackModel`, que fica como válvula
      condicionada a medir o comportamento com tool de confirmação.
      [ADR-0018](docs/adr/0018-tres-tentativas-no-429-sem-fallback-de-modelo.md).
- [x] **`D-03` = B** — erro de quota vira `503` com `Retry-After`, e a rota de
      mensagens **drena o gerador de eventos de propósito**, porque o `raise`
      do ADK está depois do `yield`.
      [ADR-0019](docs/adr/0019-erro-de-quota-vira-503-com-retry-after.md).
- [x] **`D-04` = B** — `gemini-embedding-001` com `task_type` assimétrico, em
      **768 dimensões**. [ADR-0020](docs/adr/0020-embeddings-do-gemini-embedding-001-em-768-dimensoes.md).
      **Destravou o `P4` do plano 1.4**, revisado no lugar e ainda em `rascunho`.

> **9 cenários novos em [`tests/features/modelos.feature`](tests/features/modelos.feature),
> e nenhum precisa de chave de API.** Quatro `@estrutura`: os quatro agentes no
> mesmo modelo · nenhum Flash · nenhum herdando o padrão do ADK · e o nome do
> modelo conferido contra uma lista conhecida, que é a `M-7` — erro de
> digitação passa a falhar na suíte em vez de falhar no `curl` do avaliador.
> Os outros cinco rodam contra um stub que responde `429`.

---

## Fase 3 — API

### 3.1 Casca e rotas de verificação ✅ CONCLUÍDA
- [x] FastAPI async, app factory em `app/api/aplicacao.py`, entrada em `app/main.py`.
- [x] `POST /sessoes` → `201 {"session_id": "<uuid4>"}`.
- [x] `GET /apartamentos/{n}/reservas` e `/visitantes` → `200`, lendo o repositório direto. Conferem com `RSV-1377` e Marina Duarte.
- [x] `GET /sessoes/{id}/eventos` → `200`, em ordem, conteúdo completo.
- [x] `404` nas **três** rotas com `{session_id}` — checagem única em `app/api/dependencias.py:obter_sessao_existente`, antes do miolo.
- [x] Verificado com a API no ar; OpenAPI expõe exatamente as 6 rotas do contrato + `/saude`.

| Seam | Arquivo | Impl. temporária |
|---|---|---|
| `RepositorioCondominio` | `app/dominio/repositorio.py` | `repositorio_memoria.py` |
| `ServicoSessao` | `app/dominio/sessao.py` | `sessao_memoria.py` |

- `EventoSessao.conteudo` é `dict[str, Any]` de passagem → recebe `evento_adk.model_dump(mode="json")` sem mudar o formato HTTP.
- `Sessao` é `frozen` e a interface não tem update → não existe caminho que troque o apartamento de uma sessão (base da Garantia 2).

**Decisões onde o enunciado deixa livre:** `POST /sessoes` com apartamento inexistente → **404**; rotas de verificação com apartamento inexistente → **200 lista vazia**; `session_id` = UUID4.

### 3.2 Rotas de conversa ✅ CONCLUÍDA — [spike 3.2](docs/spike-3.2-rotas-de-conversa.md) · construída no [plano 4](docs/plano-4-finalizar-o-assistente.md), passos P3 e P4 ✅ INVESTIGADA — [`docs/spike-3.2-rotas-de-conversa.md`](docs/spike-3.2-rotas-de-conversa.md)

> O harness montou o **sistema real menos o modelo**: as sete ferramentas de
> `app/agentes/ferramentas/`, o portão do ADR-0013, banco semeado de `dados/`,
> sessão do ADK em `sqlite+aiosqlite://` e a topologia do ADR-0008. Só o LLM é
> roteirizado. Toda reserva dos resultados é linha real no SQLite.

- [x] **Os três `409` são a mesma pergunta:** `id ∈ pendentes(sessão)?`. Medido
      nos três casos — id inexistente, id de outra sessão, id já respondido —
      e nos três o id simplesmente não está na lista. Uma função serve para
      montar `confirmacoes_pendentes` **e** para decidir o `409`; o escopo por
      sessão sai de graça.
- [x] ⚠️ **A checagem do `409` também evita um `500`:** injetar um id
      desconhecido levanta `ValueError: Function call not found for function
      response ids`. Sem ela, o passo 9 reprova por código HTTP errado.
- [x] **"Nada executa" já valia sem o `409`:** reenviar id já respondido não
      reexecuta (o ADK deduplica). O `409` é **contrato**, não a trava da
      Garantia 1.
- [x] **O turno que pausa não emite texto nenhum** → o `resposta: ""` do
      contrato sai de graça, por qualquer regra. O proibido é o oposto:
      preencher o campo com texto fabricado pelo código (`A-5`).
- [x] **O turno que retoma emite DUAS respostas finais** (especialista +
      principal); o de regulamento emite **uma** (o principal), porque o
      especialista é `AgentTool`. Daí a decisão de composição.
- [x] ⚠️ **A rota não acha a sessão do ADK só com `session_id`:**
      `get_session` exige `user_id` e ele **particiona** (medido: 101 com
      `user_id="302"` → `None`). Ou mapa nosso, ou `user_id` constante — e o
      constante compartilha o state `user:` entre todos os apartamentos.
- [x] **`R5` confirmada, e pior do que estava escrito:** responder a
      confirmação por texto não executa, não consome a pendência **e cria uma
      segunda** — o texto vira pedido novo e o portão confirma de novo.
- [x] **`R6` confirmada**, e o ADK tem o próprio índice
      (`index_open_interrupts`, usado pelo `adk run`): os dois **concordaram
      nos 5 casos** medidos.
- [x] ✅ **Passo 14 passa, com a corrida FORÇADA a se sobrepor** — barreira
      liberando só quando as duas gravações chegaram: duas respostas `200`,
      exatamente uma reserva. ⚠️ Medido em **SQLite**; o ADR-0014 troca por
      Postgres e isto precisa ser refeito.
- [x] Retomar **não exigiu `invocation_id`**, apesar de o `adk run` passar.

**9 restrições derivadas** (`A-1` a `A-9`). **7 cenários novos** propostos — três
são regressões que hoje não existem na suíte: o do passo 14 pela rota (não pelo
repositório), o da `R5` por texto, e o da regra `A-9`.

**3 das 4 decisões já respondidas**, e sobra **1**:

| Decisão | Escolha |
|---|---|
| `rotas/D-01` — qual texto o morador lê | ✅ **C** — só o do agente principal |
| `rotas/D-02` — como achar o apartamento de uma conversa | ✅ **A** — usuário do ADK é o apartamento, com tabela nossa |
| `rotas/D-03` — quem escreve a função que lista pendências | ⬜ **aberta** |
| `rotas/D-04` — mensagem nova com pendência aberta | ✅ **A** — processar normalmente |

> ⚠️ **A `D-01` fecha uma porta do ADR-0008.** Aquele ADR registrou a troca para
> `mode="chat"` como válvula de **uma linha** para economizar chamadas ao modelo.
> Se só o principal fala com o morador, em `chat` o texto dele deixa de existir
> e a resposta sairia vazia. Virou a regra `A-9`: trocar o modo passa a exigir
> revisar essa regra também. O ADR novo da `D-01` precisa apontar para o 0008.

> **Ordem:** as rotas não são implementáveis antes da Fase 4 — precisam dos
> agentes montados e do serviço de sessão do ADK no lugar de
> `sessao_memoria.py`. O spike torna a 3.2 **especificável** por inteiro.

---

## Fase 4 — Implementar agentes e tools ✅ CONCLUÍDA — [plano 4](docs/plano-4-finalizar-o-assistente.md), passos P1 e P2

- [ ] Montar os agentes conforme a Fase 1, respeitando **R1–R3**.
- [ ] Implementar as tools da 1.3 contra o repositório SQLite.
- [ ] Ligar o `Runner`/`App` ao `DatabaseSessionService` e trocar `sessao_memoria.py`.

---

## Fase 5 — Validação contra o fluxo do avaliador ✅ CONCLUÍDA — `scripts/validar.py`, **59 verificações verdes** ([plano 4](docs/plano-4-finalizar-o-assistente.md), passo P6)

> **"Fora de escopo" não é proibição.** O enunciado lista testes automatizados ao lado de interface visual, autenticação e deploy — tudo que o avaliador **não vai cobrar**. Nenhum item daquela lista é vedado; são dispensas. Não escrever teste por causa disso seria confundir *não exigido* com *desaconselhado*.
>
> Aqui eles não são extra: são a espinha do processo. Os 15 passos do avaliador são a régua da nota; os cenários são o que impede uma decisão tomada hoje de se perder até a implementação.

- [ ] Script que executa os passos 1–14 em ordem e imprime pass/fail por asserção.
- [ ] Cobrir os que mais quebram:
  - [ ] Passos 3/4/10: `RSV-4821`, `Marina Duarte` e `302` isolado ausentes **da resposta e dos eventos**.
  - [ ] Passo 8: reenvio do mesmo `id` → `409`, continua **exatamente uma** reserva.
  - [ ] Passos 12→13: contar eventos, reiniciar **sem restaurar**, contar de novo → mesmo número; nova mensagem funciona e o número cresce.
  - [ ] Passo 14: duas aprovações **simultâneas**, ambas `200`, soma **uma** reserva.
- [ ] Rodar em **clone limpo**, do `uv sync` em diante.

---

## Fase 6 — README final (entregável avaliado) 🟢

- [ ] Substituir o enunciado, com exatamente três seções:
  - [ ] **Arquitetura** — cada agente, responsabilidade, como é acionado e **por quê**.
  - [ ] **Garantias** — para cada uma das cinco, arquivo + trecho, e por que não depende do modelo. Os caminhos precisam existir.
        **A fonte já existe:** cada ADR em `docs/adr/` traz `Invariantes e garantias afetados` e `Onde isso vive no código`. Esta seção é a **montagem** desse material, não uma redação do zero — era a antiga 1.5 da Fase 1, que não era investigação e por isso saiu de lá.
        Antes de escrever, rodar `uv run python scripts/cobertura.py`: ele acusa invariante sem cenário e ponteiro quebrado, que são exatamente as duas formas de esta seção apontar para código que não existe (reprovação no passo 15).
  - [ ] **Como rodar** — pré-requisitos, `.env`, comando de subida, comando de restauração.
- [ ] Fork público, tudo na `main`.

---

## Investigações de risco (fora da linha principal)

### R1 — Spike da confirmação de tools ✅ — [`docs/spike-R1-confirmacao-de-tools.md`](docs/spike-R1-confirmacao-de-tools.md)

> Executado antes da arquitetura, o que em retrospecto foi fora de ordem (ver nota do topo). Os achados valem e **entram como restrição na Fase 1**.

Verificado por execução, com SQLite persistido e **reinício real de processo**: aprovar executa 1×, negar 0×, reenviar o mesmo id continua 1×.

- **R1** — ⚠️ Tool com `require_confirmation` **não pode** viver em agente embrulhado em `AgentTool`: a sessão aninhada é descartada, a pendência nunca aparece, a ação nunca executa — **sem erro**. É a "armadilha mais cara" do enunciado, com causa identificada.
- **R2** — Em `sub_agents`, `chat` e `single_turn` ambos retomam. Escolha livre.
- **R3** — Agente sem tool de confirmação (Regulamento) pode ser `AgentTool`.
- **R4** — Sessão persistida exige `sqlite+aiosqlite://` e o extra `[db]`.
- **R5** — A rota de confirmações injeta um `FunctionResponse` autorado por `"user"`; **não pode** reusar o caminho de texto da rota de mensagens.
- **R6** — `require_confirmation` é por tool e aceita callable → "confirma só se taxa > 0" sem dividir a tool.
- **Qual `id` expor:** o do `function_call` `adk_request_confirmation` (prefixo `adk-`), gravado na sessão.

**Decisões aguardando você:** D-01 a D-05 no documento. D-03 (nº de especialistas) é da Fase 1 e o spike **não** a resolveu. D-02 está bloqueada por item não verificado.

### Pendente
- [ ] Testar se eventos internos de `AgentTool` propagam para a sessão principal → destrava **D-02** e parte da Garantia 4.
- [ ] Validar com Gemini real — exige `.env` com `GOOGLE_API_KEY`, que não existe no ambiente.

---

## Paralelização

| Trilha | Conteúdo | Depende de |
|---|---|---|
| A 🔴 | Fase 1 (arquitetura) → Fase 4 (agentes) → 3.2 | decisões D-01 a D-05 |
| B 🟡 | 2.2/2.3 storage + schema | 1.1 (invariantes) |
| C 🟢 | 1.4 fatiamento do regulamento, 2.4 modelos | nada |
| D 🟢 | Fase 5 (script de validação) | contrato da API (3.1 já destrava metade) |

---

## Riscos conhecidos

1. **Confirmação que aceita e não executa** — causa identificada (R1). Mitigação: respeitar R1 e sempre testar com sessão persistida + após reinício, nunca só no `adk web`.
2. **Vazamento de dados de outro apartamento pelos eventos** — não basta filtrar a resposta; `GET /eventos` é inspecionado. A tool não pode nem *retornar* o dado ao modelo.
3. **Rate limit do Gemini** — ✅ **quantificado na 2.4.** O limite que mata não é
   o do passo 14 (por minuto): é o **diário**, 20/dia na família Flash contra
   70–85 chamadas de uma correção. E o erro não vira só 500: pode virar `200`
   com `resposta` vazia, que é o sinal de confirmação pendente (`M-4`).
4. **Race na gravação** — `SELECT` antes do `INSERT` não resolve; a unicidade tem que ser do banco.
5. **Regulamento inteiro no contexto** — qualquer atalho de "carrega o md e manda pro prompt" reprova a Garantia 4.
