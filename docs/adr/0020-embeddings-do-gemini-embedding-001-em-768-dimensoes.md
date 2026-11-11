# ADR-0020 — Os vetores do regulamento vêm do `gemini-embedding-001`, com `task_type`, em 768 dimensões

**Status:** aceito
**Data:** 2026-11-08
**Origem:** [`docs/spike-2.4-modelos-gemini.md`](../spike-2.4-modelos-gemini.md) → `modelos/D-04` — decisão **adjacente** ao escopo da 2.4, ver *Origem* abaixo
**Invariantes e garantias afetados:** `I-05`; Garantia 4 (o regulamento é consultado, nunca carregado inteiro) — por serem o que a recuperação semântica sustenta
**Relacionado:** ADR-0015 (decidiu que a recuperação é semântica) · ADR-0016 (decidiu a unidade: **artigo**, com o título do capítulo embutido, devolvendo lista) · ADR-0014 (o Postgres com `pgvector` que guarda os vetores) · completa `regulamento/D-06`, que havia decidido só a **família**

## Origem: por que esta decisão está no spike dos modelos

A 2.4 investigava **qual modelo Gemini cada agente usa**. Esta decisão é sobre um modelo que nenhum agente usa — o que gera os vetores do regulamento. O spike a levanta explicitamente como **adjacente**: é escolha de modelo Gemini, com limite de quota próprio, e a investigação dos limites passou por cima dessa informação de qualquer forma. Ficou ali em vez de virar um spike próprio de dois parágrafos.

**Quem a implementa é o passo `P4`** do [plano 1.4](../plano-1.4-postgres-e-recuperacao-semantica.md), que estava **travado exatamente nela** — o plano registrava, em voz alta, *"decisão pendente que este plano precisa antes de começar: qual modelo gera os embeddings?"*.

## Contexto

O especialista de Regulamento acha o artigo que responde a dúvida do morador por **similaridade semântica** (ADR-0015): cada artigo vira um vetor, a pergunta vira um vetor, e a busca é por proximidade, feita pelo Postgres com `pgvector` (ADR-0014). A unidade é o **artigo**, com o título do capítulo embutido no texto antes de gerar o vetor, e a recuperação devolve uma **lista** (ADR-0016). São ~96 vetores, de artigos curtos: o mediano tem ~442 caracteres.

A decisão `regulamento/D-06` já havia escolhido a **família**: Gemini, pela mesma chave do Google AI Studio que o projeto exige — e não um modelo local, que custaria ~100 MB de download e uma dependência de ML. Faltavam **o modelo** e **a dimensão**, e a dimensão não é detalhe: ela é o `vector(N)` da coluna.

Dois fatos da investigação moldam a escolha:

**O mecanismo de "tipo de tarefa" difere entre as duas gerações.** No `gemini-embedding-001` ele é o **parâmetro** `task_type` (`RETRIEVAL_DOCUMENT`, `RETRIEVAL_QUERY`, `SEMANTIC_SIMILARITY`, …), verificado como campo de `types.EmbedContentConfig` no SDK instalado. No `gemini-embedding-2`, o modelo atual, ele é **prefixo de texto no prompt** — não há parâmetro.

**A dimensão fecha ou mantém aberta a porta do índice.** O tipo `vector` do `pgvector` armazena até 16.000 dimensões, mas `hnsw` e `ivfflat` param em **2.000** (restrição `M-6`). O padrão do modelo é **3.072**.

## Decisão

| | |
|---|---|
| **Modelo** | `gemini-embedding-001` |
| **Tipo de tarefa** | `task_type='RETRIEVAL_DOCUMENT'` ao semear os artigos · `task_type='RETRIEVAL_QUERY'` ao embutir a pergunta do morador |
| **Dimensão** | **768** (`output_dimensionality=768`), e a coluna é `vector(768)` |

A assimetria é a razão de ser da escolha, não um refinamento: a busca compara **pergunta de morador** contra **texto de artigo** — dois textos de naturezas diferentes —, que é exatamente o caso para o qual `RETRIEVAL_QUERY` e `RETRIEVAL_DOCUMENT` existem.

## Alternativas consideradas

- **`gemini-embedding-2`, 768 dimensões.** É o modelo atual, sem depreciação, e aceita 8.192 tokens de entrada contra 2.048 — folga se a unidade de recuperação crescer. Rejeitada porque o controle da assimetria é **texto de prompt**, não parâmetro: ver *Decisão*, e o argumento está abaixo em *Consequências*. Some-se a armadilha `M-5`, silenciosa: passar os 96 artigos como lista de strings devolve **um** vetor agregado — a média semântica do regulamento inteiro — sem erro nenhum, e a busca passa a responder sempre a mesma coisa.
- **`gemini-embedding-2`, 3.072 dimensões (o padrão).** Nenhum parâmetro de dimensão para escolher nem justificar, e a representação mais rica que o modelo oferece. Rejeitada porque **fecha a porta do índice** (`M-6`), gasta quatro vezes mais espaço por vetor, e herda os dois contras da alternativa anterior.
- **Modelo local** (`sentence-transformers` ou similar), que tornaria a recuperação testável offline. Rejeitada antes desta decisão, em `regulamento/D-06`: ~100 MB no `uv sync` e uma dependência pesada num projeto com seis, para evitar chamadas de API que acontecem uma vez — e o `.env` do avaliador já está preenchido quando a restauração roda (passo 1 do roteiro).

**Qualidade de vetor não foi o critério de desempate, e vale dizer por quê:** para ~96 artigos curtos, os três candidatos acertam ou erram pelos **mesmos motivos**. Decidir por qualidade seria escolher com base num número que ninguém mediu.

## Consequências

**O que fica mais fácil:** a assimetria da busca passa a ser **parâmetro verificável em código**, não instrução em texto. Num projeto cuja tese é que *regra em prompt não conta*, preferir o mecanismo que o código controla é coerente — e é frase defensável no README, que é entregável avaliado. Some-se que o modelo devolve **um vetor por item** de uma lista de strings, sem o embrulho em `Content` que a geração nova exige.

**Esta decisão mata a restrição `M-5`.** Ela valia só para o `gemini-embedding-2` — lista de strings devolve um vetor agregado, sem erro — e **deixa de existir** com o `001`. Não é uma restrição mitigada nem protegida por teste: ela sai do conjunto, porque o modelo que a criava não está mais no desenho. Se alguém um dia migrar para o `-2`, ela volta, e volta junto com a necessidade de confirmar por execução o que hoje é só documentação (ver abaixo).

**O que fica mais difícil, ou passa a custar atenção:** o modelo é **depreciado**, com desligamento marcado para **2028-05-14**. É muito depois deste trabalho — entregue em 2026 —, mas *"escolhi o depreciado"* é uma frase que precisa de justificativa escrita no README, não de silêncio. E o limite de entrada cai para 2.048 tokens: sobra com folga para o artigo mediano (~442 caracteres), mas o capítulo inteiro (~3.223 caracteres, ≈950 tokens) deixa de caber com margem confortável se alguém voltar a recuperar por capítulo — o que o ADR-0016 já rejeitou por outros motivos.

**Risco aceito:** **os espaços de embedding são incompatíveis entre modelos.** Trocar de modelo depois — por depreciação, por qualidade ou por migração para o `-2` — exige **regerar todos os vetores**, porque um vetor do `001` e um vetor do `-2` não são comparáveis. Aceita-se porque regerar 96 vetores custa uma requisição (medido: o SDK transforma uma lista em **uma** chamada a `:batchEmbedContents`) e um comando de restauração.

**Sobre a dimensão:** 768 em vez de 3.072 **não é desempenho**. Para 96 artigos a varredura exata é instantânea, e o plano 1.4 já prevê "índice vetorial, se o volume justificar". O que se preserva é **opção futura** — acima de 2.000 dimensões o `pgvector` não aceita `hnsw` nem `ivfflat` (`M-6`), e `vector(3072)` grava e consulta mas nunca indexa. De quebra, 768 gasta um quarto do espaço. É escolha de porta aberta, barata, e é assim que deve ser lida.

## Verificação

| Cenário | Protege | Tipo |
|---|---|---|
| A coluna de vetor do regulamento tem 768 dimensões | `M-6` e a decisão de dimensão | **regressão** — falha se alguém voltar ao padrão de 3.072, que não indexa |
| O seed do regulamento grava um vetor para cada artigo | ADR-0016 (unidade = artigo) e a geração dos vetores | positivo — é também o critério de pronto do `P4` do plano 1.4 |
| Semear usa `RETRIEVAL_DOCUMENT` e buscar usa `RETRIEVAL_QUERY` | **a razão desta decisão** | **regressão** — falha se a assimetria virar prefixo de prompt ou desaparecer |

Arquivo: `tests/features/regulamento.feature`

Os três rodam **sem chave de API**: observam o schema gravado e o `task_type` enviado ao cliente de embedding, não a qualidade do vetor.

## Onde isso vive no código

| O quê | Onde |
|---|---|
| Nome do modelo e dimensão, num lugar só | `app/infra/embeddings.py` → `MODELO`, `DIMENSOES` |
| `vector(768)` na tabela `regulamento_trecho` | `app/infra/banco.py` → `DDL`, importando `DIMENSOES` |
| Geração com `RETRIEVAL_DOCUMENT` | `app/infra/embeddings.py` → `gerar_de_documentos`, chamado por `semear_regulamento` |
| Conversão da pergunta com `RETRIEVAL_QUERY` | `app/infra/embeddings.py` → `gerar_de_consulta` |
| Recusa com instrução quando falta a chave | `app/infra/embeddings.py` → `ChaveDeApiAusente`, `MENSAGEM_SEM_CHAVE` |
| A chave, lida do `.env` | `app/config.py` → `Configuracao.google_api_key` |

⚠️ **A dimensão é importada, não repetida.** `app/infra/banco.py` importa
`DIMENSOES` de `embeddings.py` porque schema e chamada ao modelo **precisam**
concordar: se divergirem, o Postgres recusa toda gravação. Com dois literais,
nada impediria a divergência.

**As três afirmações que estavam em *Não verificado* foram medidas** contra o
servidor, em 2026-11-08, antes de haver qualquer vetor gravado:

| Afirmação | Resultado |
|---|---|
| `output_dimensionality=768` devolve 768 números | ✅ confirmado |
| uma lista de N textos devolve N vetores distintos | ✅ 3 textos → 3 vetores distintos |
| `task_type` é aceito nos dois valores | ✅ `RETRIEVAL_DOCUMENT` e `RETRIEVAL_QUERY` |

E a busca funciona: a pergunta *"até que horas a piscina funciona?"* deu
cosseno **0,774** contra o artigo da piscina, contra 0,54–0,57 nos outros dois
do teste. Depois, sobre os 96 artigos reais, acertos dentro do escopo ficaram
em 0,699–0,763 e fora do escopo em 0,556–0,598.

⚠️ **Bug real que esta decisão expôs, e que vale mais que ela.** Ligar a
geração de embeddings foi a primeira coisa do projeto a de fato precisar da
chave — e descobriu que **o `.env` nunca era carregado no `os.environ`**. O
`google-genai` lê de lá; `app/config.py` afirmava, por escrito, que não
precisava ler a chave "porque o SDK a lê direto". Resultado: com uma chave
válida no arquivo, `aurora-restaurar` recusava dizendo que não havia chave — e
o passo 1 do roteiro do avaliador é exatamente *preencher o `.env` e
restaurar*. O erro era invisível porque a mensagem era **plausível**: quem a
lesse conferiria o arquivo, veria a chave, e não teria pista. Corrigido, e o
cenário `A chave do .env chega a quem gera os embeddings` existe para não
voltar.

⚠️ **Resta uma dependência não verificada, e ela é da alternativa rejeitada.**
Que o `gemini-embedding-2` devolva um vetor por `Content` separado segue sendo
afirmação da documentação, **sem execução contra o servidor**. Esta decisão não
depende disso — o `001` devolve um vetor por item, agora medido —, mas uma
migração futura para o `-2` depende, e precisa ser confirmada **antes** de
haver 96 vetores gravados que podem ser todos o mesmo. A rede contra isso já
existe: `EmbeddingGemini._gerar` levanta exceção se vierem menos vetores que
textos, e o cenário `nenhum vetor gravado é idêntico ao de outro trecho` pega
o resultado.
