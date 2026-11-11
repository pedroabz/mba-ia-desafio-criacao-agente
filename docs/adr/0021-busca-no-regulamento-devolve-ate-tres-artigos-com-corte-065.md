# ADR-0021 — A busca no regulamento devolve até três artigos, com corte absoluto de 0,65

**Status:** aceito
**Data:** 2026-11-08
**Origem:** [`docs/spike-1.4-estrategia-regulamento.md`](../spike-1.4-estrategia-regulamento.md) → `regulamento/D-08`, que decidiu **medir depois que os vetores existissem**. Eles existem desde a execução do [plano 1.4](../plano-1.4-postgres-e-recuperacao-semantica.md), e a medição está abaixo.
**Invariantes e garantias afetados:** `I-05`; Garantia 4
**Relacionado:** ADR-0015 (a recuperação é semântica), ADR-0016 (a unidade é o artigo e a resposta é uma lista), ADR-0020 (o modelo e a dimensão)

## Contexto

O especialista de Regulamento acha o artigo que responde a dúvida do morador
por similaridade de cosseno. Duas perguntas ficaram em aberto desde o spike
1.4, e a `D-08` decidiu **não** respondê-las no escuro: **quantos** artigos a
busca devolve, e **quando** ela diz que não achou nada.

O requisito que as duas servem está no enunciado: a ferramenta não pode trazer
trechos "de capítulos que tratam de outros assuntos" (Garantia 4), e o
regulamento nunca entra inteiro no contexto (`I-05`). E há um modo de falha
pior que o óbvio: **"achei errado" é pior que "não achei"**. O segundo o modelo
contorna dizendo que não encontrou; o primeiro chega ao morador como resposta.

A `D-03`, antecessora desta, tinha limiares calibrados sobre a busca léxica —
`0,568`, `0,053`, `0,000`. Cosseno tem distribuição completamente diferente e
não chega perto de zero nem para textos sem relação. Aqueles números foram
descartados, e é por isso que esta decisão esperou a medição.

## A medição

Nove perguntas contra os 96 artigos reais, vetorizados com
`gemini-embedding-001` em 768 dimensões. Similaridade do melhor artigo:

| Pergunta | Melhor acerto | Artigo |
|---|---|---|
| quanto barulho posso fazer de noite | **0,7629** | Art. 16 · Cap. III |
| até que horas a piscina funciona aos domingos? | **0,7529** | Art. 22 · Cap. IV |
| posso ter cachorro no apartamento | **0,7353** | Art. 52 · Cap. VIII |
| preciso avisar sobre mudança? | **0,7297** | Art. 61 · Cap. IX |
| pode levar cachorro na quadra? | **0,7246** | Art. 56 · Cap. VIII |
| onde guardo meu carro | **0,6990** | Art. 80 · Cap. XI |
| oi, tudo bem? | 0,5980 | Art. 7 · Cap. I |
| qual o telefone da pizzaria | 0,5710 | Art. 47 · Cap. VII |
| quanto custa o bitcoin hoje | 0,5595 | Art. 62 · Cap. IX |

Dentro do escopo: **0,699 a 0,763**. Fora: **0,556 a 0,598**. Vão de **0,10**
entre o pior acerto legítimo e o melhor falso positivo, sem sobreposição.

**O segundo achado é o que decide o formato do corte.** A pergunta fora de
escopo não produz só nota baixa: produz uma lista **chata**. Os três primeiros
colocados ficam quase empatados, porque nenhum artigo tem a ver com a pergunta
e a ordem é praticamente ruído:

| Pergunta | 1º | 2º | 3º | Queda do 1º ao 3º |
|---|---|---|---|---|
| até que horas a piscina… | 0,7529 | 0,6961 | 0,6661 | **0,0868** |
| quanto custa o bitcoin hoje | 0,5595 | 0,5575 | 0,5558 | **0,0037** |
| qual o telefone da pizzaria | 0,5710 | 0,5672 | 0,5658 | 0,0052 |

Pergunta com resposta tem um vencedor claro e cai rápido. Pergunta sem
resposta tem três quase-empates.

## Decisão

A busca devolve **no máximo 3 artigos**, e **somente os com similaridade de
cosseno ≥ 0,65**. Se nenhum artigo alcançar o corte, ela devolve **lista
vazia**, e o especialista responde que não encontrou aquilo no regulamento.

O corte é **absoluto**, não relativo ao melhor resultado.

## Alternativas consideradas

- **Devolver só o artigo mais parecido.** Mais simples, e impossível trazer
  assunto alheio. Rejeitada por medição: o spike 1.4 achou perguntas cuja
  resposta exige **dois** artigos (Art. 39 junto com Art. 16), e com um só a
  resposta ao morador fica pela metade. O ADR-0016 já havia decidido que a
  recuperação devolve uma **lista** justamente por isso.
- **Devolver o melhor sempre, sem corte.** Nunca responde "não sei". Rejeitada
  porque é o modo de falha caro: *"quanto custa o bitcoin hoje"* receberia o
  Art. 62 (Mudanças), com 0,5595, e o morador leria isso como resposta. A
  pergunta fora de escopo **não some** por não ter resposta — ela pega o artigo
  menos distante.
- **Corte relativo: só artigos dentro de uma margem do melhor** (por exemplo,
  10%). Atraente porque se adapta a cada pergunta, sem número mágico.
  **Rejeitada pela própria medição, e por um motivo que não era óbvio:** ela
  falha exatamente no caso que mais importa. Os três primeiros do "bitcoin"
  estão a **0,37%** um do outro — um corte relativo de 10% devolveria **os
  três**, todos irrelevantes. E na pergunta da piscina, onde a queda é de
  8,7%, o mesmo corte descartaria o segundo artigo legítimo. O corte relativo
  é mais generoso justamente quando devia ser mais severo.
- **Corte mais alto, 0,70.** Deixaria 0,10 de margem acima dos falsos
  positivos. Rejeitada porque cortaria *"onde guardo meu carro"*, que acerta o
  Capítulo XI com 0,6990 — perder uma pergunta legítima para ganhar margem
  contra ruído que já está 0,10 abaixo é troca ruim.

## Consequências

**O que fica mais fácil:** "não achei" passa a ser um estado de verdade, com
critério, em vez de uma frase que o modelo inventa. E a lista curta mantém a
Garantia 4 por construção: três artigos, cada um com o seu capítulo, nunca um
capítulo inteiro.

**O que fica mais difícil, ou passa a custar atenção:** 0,65 é um número
calibrado para **este** modelo de embedding, nesta dimensão. Trocar o modelo
invalida o corte junto com os vetores — e o ADR-0020 já registra que trocar de
modelo exige regerar tudo. O corte entra na mesma lista de coisas a refazer.

**Risco aceito:** a medição são **nove** perguntas, não uma suíte de
centenas. O vão de 0,10 é confortável, mas é um vão medido sobre nove pontos.
Uma pergunta legítima com vocabulário muito distante do regulamento pode cair
abaixo de 0,65 e receber "não encontrei" — que é o **lado certo** de errar: o
morador reformula, em vez de receber o artigo errado com cara de resposta.

**Nada aqui depende de prompt.** O corte e o limite de três são do código que
consulta o banco. Nenhuma mensagem do morador os altera, o que é a tese do
projeto aplicada a esta decisão.

## Verificação

| Cenário | Protege | Tipo |
|---|---|---|
| A dúvida da piscina aos domingos recupera o trecho que a responde | a decisão deste ADR | positivo |
| Pergunta com vocabulário divergente recupera o trecho certo | o corte não é alto demais | positivo |
| Pergunta cuja resposta exige dois artigos recupera os dois | o limite de 3 e a lista do ADR-0016 | positivo |
| A resposta está num capítulo que a pergunta não menciona | a recuperação semântica (ADR-0015) | positivo |
| Pergunta fora de escopo não devolve trecho nenhum | o corte de 0,65 | **regressão** — falha se alguém tirar o corte |
| O recorte nunca devolve o regulamento inteiro | `I-05`, Garantia 4 | **regressão** |
| O recorte da piscina não arrasta capítulos de outros assuntos | Garantia 4 | **regressão** |

Arquivo: `tests/features/regulamento.feature`

## Onde isso vive no código

| O quê | Onde |
|---|---|
| O corte e o limite, num lugar só | `app/infra/recuperacao.py` → `CORTE_DE_SIMILARIDADE`, `MAXIMO_DE_ARTIGOS` |
| A consulta por proximidade | `app/infra/recuperacao.py` → `_por_similaridade` |
| A ferramenta `buscar_no_regulamento` | `app/agentes/ferramentas/regulamento.py` |
| Seguir remissão de capítulo | `app/infra/recuperacao.py` → `remissao_de_capitulo` ([ADR-0022](0022-a-busca-segue-remissoes-explicitas-de-capitulo.md)) |

⚠️ **O corte é um número no código, e o Postgres não tem como impô-lo.**
Diferente do `vector(768)`, que o banco recusa se estiver errado, `0,65` é uma
constante que alguém pode mudar sem nada quebrar. O cenário `Pergunta fora de
escopo não devolve trecho nenhum` é a única rede — verificado por sabotagem:
zerar o corte derruba exatamente os três casos fora de escopo, e a busca passa
a responder "Art. 62 · Mudanças" para *"quanto custa o bitcoin"*.

**O teto de 3 continua valendo mesmo com a remissão do ADR-0022**: o artigo
trazido pela remissão ocupa a última vaga, não acrescenta uma quarta.

⚠️ **O corte é um número no código, e o Postgres não tem como impô-lo.**
Diferente do `vector(768)`, que o banco recusa se estiver errado, `0,65` é uma
constante que alguém pode mudar sem nada quebrar. O cenário `Pergunta fora de
escopo não devolve trecho nenhum` é a única rede, e por isso ele é de
regressão: tirar o corte faz a busca responder "Art. 62 · Mudanças" para
*"quanto custa o bitcoin"*, e esse cenário é o que grita.
