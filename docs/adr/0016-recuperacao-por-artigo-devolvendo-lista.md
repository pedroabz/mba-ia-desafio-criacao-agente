# ADR-0016 — A recuperação é por artigo e devolve uma lista; a resposta cita, e só transcreve sob pedido

**Status:** aceito
**Data:** 2026-11-08
**Origem:** [`docs/spike-1.4-estrategia-regulamento.md`](../spike-1.4-estrategia-regulamento.md) → `regulamento/D-06`, `D-07`, `D-08`, `D-09`
**Invariantes e garantias afetados:** `I-05`; Garantia 4
**Relacionado:** ADR-0015 (decidiu que a recuperação é semântica) · ADR-0008 (o `AgentTool` que isola o recuperado)

## Contexto

O ADR-0015 decidiu que o regulamento é recuperado por similaridade semântica. Faltava dizer **o que** é recuperado, **quanto**, e **o que a resposta faz com isso**.

A investigação original tinha recomendado recuperar **capítulos inteiros**, e o motivo era um defeito do método léxico: recortar por artigo deixava pouca superfície de palavras para casar. Com embeddings esse argumento deixou de existir — e o exame do documento mostrou dois casos que o derrubam de vez.

**Uma pergunta pode exigir artigos de capítulos diferentes.** *"Posso fazer festa com som no salão até 2h?"* precisa de dois:

| Artigo | Onde | O que diz |
|---|---|---|
| Art. 39 | Cap. VI — Salão de festas | *"deve respeitar o período de silêncio **previsto no Capítulo III**"* — remete e **não dá o horário** |
| Art. 16 | Cap. III — Silêncio | *"período de silêncio é o intervalo entre **22h e 8h**"* — tem a resposta |

Nenhum dos dois responde sozinho.

**E a resposta pode morar num capítulo que a pergunta não menciona.** *"Meu cachorro pode ir na quadra?"* se responde pelo **Art. 56**, que vive no Cap. VIII (Animais). O Cap. VI, sobre a quadra, tem **zero** menções a animais em seus oito artigos. Recuperando por capítulo, a busca por "quadra" traria o Cap. VI — que não responde — e o capítulo certo nem apareceria no topo.

Há ainda o problema de **borramento**: um vetor por capítulo representa a média dos assuntos dele. O Cap. IV mistura horário de funcionamento, exame dermatológico, trajes de banho e limite de convidados num vetor só — exatamente o que embeddings fazem mal.

## Decisão

| | |
|---|---|
| **Modelo de embedding** | Gemini, pela mesma chave do Google AI Studio que o projeto já exige |
| **Unidade de recuperação** | **artigo**, com o título do capítulo embutido no texto antes de gerar o vetor |
| **Quantidade** | uma **lista** de artigos, nunca um só |
| **Quantos e qual o corte** | **a medir**, depois que os vetores existirem |
| **Citação na resposta** | prosa curta citando o artigo; transcrição **só sob pedido explícito**, e limitada ao artigo |

O título do capítulo entra no texto do artigo para que remissões não se percam: o Art. 39 recuperado sozinho precisa carregar que pertence ao capítulo do salão de festas.

> **Anotação de 2026-11-08: a primeira linha da tabela ficou mais específica
> em outro ADR.** "Modelo de embedding: Gemini" era a **família**; o modelo e a
> dimensão foram decididos em
> [ADR-0020](0020-embeddings-do-gemini-embedding-001-em-768-dimensoes.md) —
> `gemini-embedding-001`, com `task_type='RETRIEVAL_DOCUMENT'` ao semear e
> `'RETRIEVAL_QUERY'` ao buscar, em **768 dimensões**. A decisão deste ADR não
> muda; o ADR-0020 a completa, e é dele que sai o `vector(768)` da coluna.
>
> Um detalhe que a unidade decidida aqui torna confortável: o limite de entrada
> do `gemini-embedding-001` é de 2.048 tokens, e o artigo mediano tem ~442
> caracteres. Recuperar por **capítulo** — a alternativa que este ADR rejeitou —
> chegaria a ~3.223 caracteres (≈950 tokens) e deixaria muito menos folga.

## Alternativas consideradas

- **Recuperar capítulos inteiros.** Era a recomendação original. Rejeitada pelos dois casos do contexto e pelo borramento: um capítulo é vários assuntos num vetor só.
- **Recuperar um artigo só, o mais próximo.** Mais simples e previsível. Rejeitada pelo caso Art. 39 + Art. 16 — uma pergunta legítima cuja resposta exige dois artigos ficaria sem resposta, e o modo de falha seria dar meia resposta como se fosse inteira.
- **OpenAI para os embeddings.** O usuário tem créditos. Rejeitada por um motivo que não é custo: o passo 1 do roteiro do avaliador diz que ele *"preenche a própria chave"*, no singular e no contexto do Google AI Studio. Exigir uma `OPENAI_API_KEY` que ele provavelmente não tem faz a restauração falhar e a correção parar no primeiro passo. Some-se que o enunciado lista "Modelos Gemini, com chave do Google AI Studio" entre as tecnologias obrigatórias, e um segundo provedor fica visível no `pyproject.toml`.
- **Sempre transcrever o trecho entre aspas.** O morador leria a regra literal. Rejeitada como padrão porque, quando a recuperação erra, o texto errado entra nos eventos da sessão — e aí não é resposta ruim, é critério de aceite reprovado. Fica disponível sob pedido, onde o risco se restringe aos turnos em que o morador pede detalhe.
- **Decidir agora os limiares de corte.** Rejeitada porque a faixa útil de similaridade de cosseno depende do modelo de embedding e do tamanho do trecho, e os números medidos antes eram do método léxico — não transferem.

## Consequências

**O que fica mais fácil:** cada vetor representa **um** assunto, não a média de oito. Perguntas cuja resposta atravessa capítulos passam a ser respondíveis. E a transcrição sob pedido fica segura **por construção**: recuperando por artigo, "transcrever o que foi recuperado" já é um recorte pequeno — não existe caminho que cole 3 KB de capítulo.

**O que fica mais difícil, ou passa a custar atenção:** 96 vetores em vez de 14, e dois parâmetros — quantos artigos na lista e qual o corte de "não achei" — que ficam **indefinidos** até serem medidos. Enquanto isso, a ferramenta existe com valores provisórios, e provisório tem o hábito de virar permanente.

A válvula de transcrição também precisa de disciplina: sem pedido explícito, a resposta é prosa. Se o especialista passar a transcrever por padrão, a decisão vira a alternativa que foi rejeitada, sem ninguém notar — daí o cenário de regressão para o caminho sem pedido.

**Risco aceito:** a lista pode trazer artigos irrelevantes junto com o certo, e o modelo precisa escolher entre eles ao redigir. Isso devolve ao modelo um pedaço do julgamento que a recuperação deveria ter feito. Aceita-se porque a alternativa — devolver um só — tem modo de falha pior: meia resposta apresentada como inteira.

## Verificação

| Cenário | Protege | Tipo |
|---|---|---|
| Pergunta cuja resposta exige dois artigos recupera os dois | **a razão desta decisão** | **regressão** — falha se voltar a devolver um trecho só |
| A resposta está num capítulo que a pergunta não menciona | **a razão de ser por artigo** | **regressão** — falha se voltar a recuperar por capítulo |
| A resposta cita o artigo sem colar o capítulo | Garantia 4, `I-05` | **regressão** |
| Sob pedido, o especialista transcreve o artigo — e só ele | a válvula | positivo |
| Sem pedido, a resposta não transcreve o regulamento | a válvula não virar padrão | **regressão** |

Arquivo: `tests/features/regulamento.feature`

## Onde isso vive no código

| O quê | Onde |
|---|---|
| Fatiamento por **artigo** | `app/dominio/regulamento.py` → `fatiar_em_artigos` |
| O capítulo embutido no texto do vetor | `app/dominio/regulamento.py` → `TrechoRegulamento.texto_para_vetor` |
| Uma linha por artigo, com o capítulo | `app/infra/banco.py` → tabela `regulamento_trecho` |
| Devolver uma LISTA de artigos | `app/agentes/ferramentas/regulamento.py` → `buscar_no_regulamento` |

**Medido sobre o documento real:** o fatiador acha **96 artigos** em **14
capítulos**, nenhum com texto vazio e nenhum título repetido. O texto mediano
tem 472 caracteres e o maior 1.128 — folga larga nos 2.048 tokens que o
`gemini-embedding-001` aceita (ADR-0020), então nenhum artigo é truncado.

O fatiador é função **pura**: recebe o markdown, devolve estrutura. Não faz
I/O e não chama modelo, o que é o que permite testá-lo sem banco e sem chave.

**Por que o capítulo entra no vetor**, concretamente: *"Art. 22 A piscina
observa os seguintes períodos de uso…"* sozinho não diz do que trata — o vetor
dele ficaria ambíguo entre piscina, academia e salão. Com `Capítulo IV:
Piscina` na frente, a pergunta *"até que horas a piscina funciona aos
domingos?"* recupera esse artigo com 0,753 de similaridade, contra 0,696 do
segundo colocado do mesmo capítulo.

⚠️ **A metade de "devolver uma lista" segue não implementada.** Ela vive na
ferramenta `buscar_no_regulamento`, que depende de `regulamento/D-08` (quantos
artigos devolver e qual o corte) — pendente. O fatiamento, que é a outra
metade deste ADR, está inteiro.

Verificado indiretamente pelos 3 cenários de `tests/features/regulamento.feature`
que ficaram verdes: eles conferem que existe um trecho gravado **para cada
artigo** do documento, nem mais nem menos.
