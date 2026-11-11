# ADR-0015 — O regulamento é recuperado por similaridade semântica, não por casamento de palavras

**Status:** aceito
**Data:** 2026-11-08
**Origem:** [`docs/spike-1.4-estrategia-regulamento.md`](../spike-1.4-estrategia-regulamento.md) → `regulamento/D-02` e `D-04`
**Invariantes e garantias afetados:** `I-05`; Garantia 4
**Relacionado:** ADR-0008 (o Regulamento é `AgentTool`, que isola o recuperado) · ADR-0014 (o Postgres que guarda os vetores)

## Contexto

O assistente responde dúvidas sobre o regulamento interno do condomínio — um documento de 14 capítulos, 96 artigos e cerca de 43 mil caracteres. A Garantia 4 do enunciado proíbe carregá-lo inteiro: ele deve ser **consultado**, recuperando apenas o trecho que responde à pergunta.

A pergunta era **como achar esse trecho**. A investigação começou pelo caminho mais simples — comparar as palavras da pergunta com as palavras de cada capítulo — e mediu o resultado: **86% de acerto** quando a pergunta chega com a fala crua do morador.

A causa do erro não é o algoritmo: é que **o vocabulário do morador não é o vocabulário da lei**. Seis palavras óbvias de quem mora num prédio têm **zero ocorrências** no documento:

| Palavra | Ocorrências | Como o regulamento diz |
|---|---|---|
| `horas`, `horário` | 0 | *"a piscina funciona das 9h às 20h"* |
| `cachorro`, `gato` | 0 | *"animais de estimação"* |
| `barulho` | 0 | *"perturbação do sossego"* |
| `carro` | 0 | *"veículos"* |

E a pergunta que o próprio roteiro do avaliador usa, no passo 12, é *"até que **horas** a piscina funciona aos domingos?"*. Ela só funciona por coincidência: a palavra `piscina` aparece 20 vezes no capítulo que a responde, e carrega sozinha a consulta.

Um método cujo ponto cego são justamente as palavras que as pessoas usam não é um método: é sorte com etapas.

## Decisão

A recuperação é **semântica, por embeddings**. Cada trecho do regulamento é convertido num vetor que representa o assunto; a pergunta é convertida da mesma forma; a busca é por proximidade (similaridade de cosseno), feita pelo Postgres com `pgvector` (ADR-0014).

Os vetores são **gerados e persistidos** — não recalculados a cada consulta nem a cada subida da aplicação.

O que isso resolve: *"horas"* fica próximo de *"funciona das 9h às 20h"* porque o modelo que gerou os vetores aprendeu que falam da mesma coisa, sem que a palavra apareça em lugar nenhum.

## Alternativas consideradas

- **Busca léxica sobre título e corpo.** Era a recomendação do spike: nenhuma dependência nova, índice montado em 4,9 ms, busca em 0,01 ms, determinística e testável sem chave de API. Rejeitada pelo defeito descrito no contexto — 86% de acerto, com erros **silenciosos**: devolve um capítulo plausível e errado. *"Fumar no elevador"* cai no capítulo de Mudanças; *"reformar o banheiro"* pontua zero em todos os 14.
- **Busca léxica mais uma tabela de apelidos curada à mão** (`cachorro → animal de estimação`). Subia a medição para 93%. Rejeitada por dois motivos, e o segundo é decisivo: a lista **não tem como estar completa** — cobre o vocabulário que alguém imaginou —, e a própria investigação registrou que a tabela e a suíte de perguntas que a mediu foram escritas na mesma sessão, pela mesma pessoa. O número media a si mesmo. Além disso, sinônimos mantidos à mão são exatamente a "disciplina em vez de mecanismo" que este projeto evita em todo o resto.
- **O modelo escolher o capítulo a partir de um índice de 14 títulos.** Resolveria o vocabulário sem infraestrutura nenhuma — o modelo já está no turno e entende que "horas" tem a ver com "Piscina". É a alternativa mais barata e foi seriamente considerada. Rejeitada porque mistura recuperação com geração: a qualidade da busca deixa de ser testável isoladamente, e passa a variar com o modelo, a temperatura e o tamanho do contexto. Com embeddings, a recuperação é um componente com entrada e saída próprias, que se mede sem conversar.

> Registro de uma objeção que o spike levantou contra essa última alternativa e que **não se sustenta**: *"desloca a correção para o modelo, que é o que o tema do desafio desaconselha"*. O princípio *"o código decide o que é permitido"* protege **garantias** — quem pode cancelar o quê, o que exige confirmação. Escolher qual capítulo responde uma dúvida não é regra que se fure: é julgamento de relevância. E, como o Regulamento é `AgentTool` (ADR-0008), um capítulo errado sequer chega aos eventos da sessão. A alternativa foi rejeitada por testabilidade, não por esse argumento.

## Consequências

**O que fica mais fácil:** o morador pergunta com as palavras dele. A recuperação deixa de depender de o modelo traduzir a pergunta para o juridiquês do documento antes de chamar a ferramenta — comportamento que nunca foi medido e sobre o qual a decisão anterior se apoiava.

**O que fica mais difícil, ou passa a custar atenção:** gerar embeddings exige um modelo. Isso acrescenta ou uma dependência de execução (modelo local, com download pesado) ou chamadas de API no caminho de preparação dos dados. E **a recuperação deixa de ser testável sem esse modelo**: a busca léxica rodava offline e determinística; a semântica não.

Some-se que os parâmetros medidos para a busca léxica — limiares de corte, quantos capítulos devolver — **não transferem**. Similaridade de cosseno tem distribuição diferente, e tipicamente não chega perto de zero nem para textos sem relação. Os cortes precisam ser medidos de novo.

**Risco aceito:** a qualidade da recuperação passa a depender de um modelo externo e não é verificável por inspeção de código. Um teste que afirme "a pergunta da piscina recupera o Capítulo IV" vira um teste sobre o modelo de embedding, não sobre a nossa lógica. Mitigação: persistir os vetores (ADR-0014) torna a busca **reprodutível** — com os mesmos vetores, a mesma pergunta devolve sempre o mesmo trecho, e o teste volta a ser determinístico sobre o conjunto gravado.

## Verificação

| Cenário | Protege | Tipo |
|---|---|---|
| A pergunta do passo 12 recupera o trecho que a responde | a decisão deste ADR | positivo |
| Pergunta com vocabulário divergente recupera o trecho certo | **o motivo desta decisão** | **regressão** — falha se a recuperação voltar a ser léxica |
| Pergunta fora do domínio não devolve trecho nenhum | `I-05`, Garantia 4 | **regressão** |
| O recorte nunca devolve o documento inteiro | `I-05`, Garantia 4 | **regressão** |

Arquivo: `tests/features/regulamento.feature`

## Decisões que este ADR deixa em aberto

> **Anotação de 2026-11-08: os três pontos abaixo já foram respondidos, e esta
> seção ficou datada.** Ela fica como está, porque ADR aceito não se reescreve —
> o que vale é o ponteiro:
>
> - **`D-01` (unidade de recuperação)** foi substituída pela `D-07` e decidida:
>   **artigo**, com o título do capítulo embutido no vetor, devolvendo uma
>   lista. Ver [ADR-0016](0016-recuperacao-por-artigo-devolvendo-lista.md).
> - **`D-03` (quantos trechos e qual o corte)** virou `D-08`, decidida como
>   **"a medir depois que os vetores existirem"**. Também no ADR-0016.
> - **`D-05` (política de citação)** virou `D-09`, decidida: prosa curta
>   citando o artigo, transcrição só sob pedido. Também no ADR-0016.
>
> E o **modelo** que este ADR exige sem nomear — *"gerar embeddings exige um
> modelo"* — foi escolhido em
> [ADR-0020](0020-embeddings-do-gemini-embedding-001-em-768-dimensoes.md):
> `gemini-embedding-001`, com `task_type` assimétrico e **768 dimensões**.

Três pontos continuam pendentes no spike 1.4 e **não** são resolvidos aqui:

- **`D-01` — unidade de recuperação** (capítulo inteiro ou artigo). A análise original favorecia capítulo por um defeito do método léxico que não existe mais; precisa ser reexaminada.
- **`D-03` — quantos trechos devolver e qual o corte de "não achei"**. Os limiares medidos eram do método léxico e não transferem.
- **`D-05` — política de citação na resposta**, inalterada pela mudança e ainda pendente.

## Onde isso vive no código

| O quê | Onde |
|---|---|
| Tabela dos trechos, com `embedding vector(768)` | `app/infra/banco.py` → `DDL`, tabela `regulamento_trecho` |
| Geração dos vetores | `app/infra/embeddings.py` → `EmbeddingGemini` |
| A interface que permite semear sem chave | `app/infra/embeddings.py` → `ClienteEmbedding` |
| Indexação dentro da restauração | `app/infra/seed.py` → `semear_regulamento` |
| Ligação ao comando | `app/cli.py` → `restaurar` (`uv run aurora-restaurar`) |
| A busca por proximidade | `app/infra/recuperacao.py` → `RecuperadorDeRegulamento.buscar` |
| A ferramenta que o especialista chama | `app/agentes/ferramentas/regulamento.py` |

**Medido contra os vetores reais, em 2026-11-08.** Os 96 artigos foram
indexados em **uma** requisição ao modelo, em menos de 5 segundos, e a busca
por cosseno separa limpo:

| | melhor acerto |
|---|---|
| perguntas dentro do escopo (6 casos) | 0,699 – 0,763 |
| perguntas fora do escopo (3 casos) | 0,556 – 0,598 |

Inclusive o caso que derrubou a busca léxica no spike 1.4: *"pode levar
cachorro na quadra?"* recupera o **Art. 56**, do Capítulo VIII (Animais) — um
capítulo que a pergunta não menciona, e cujo vocabulário não aparece no
Capítulo VI, que fala da quadra.

⚠️ **A ferramenta `buscar_no_regulamento` não existe**, de propósito. Quantos
artigos devolver e qual o corte de "não achei" é `regulamento/D-08`, decidida
como *"a medir depois que os vetores existirem"* — e a medição acima é
justamente o insumo dela. **A escolha do corte segue pendente**; os 7 cenários
`@recuperacao` seguem vermelhos até ela.

Verificado por 3 cenários em `tests/features/regulamento.feature`, todos
verdes: o seed grava um vetor por artigo, a coluna tem 768 dimensões, e a
assimetria do `task_type` vale nos dois sentidos.
