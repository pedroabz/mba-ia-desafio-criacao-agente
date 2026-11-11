# ADR-0022 — A busca segue as remissões explícitas de capítulo

**Status:** aceito
**Data:** 2026-11-08
**Origem:** a execução do passo `P1` do [plano 4](../plano-4-finalizar-o-assistente.md). Não saiu de spike: saiu de um cenário vermelho que a implementação não conseguia fazer passar sem decidir algo.
**Invariantes e garantias afetados:** `I-05`; Garantia 4
**Relacionado:** [ADR-0016](0016-recuperacao-por-artigo-devolvendo-lista.md) (a unidade é o artigo e o capítulo entra no vetor), [ADR-0021](0021-busca-no-regulamento-devolve-ate-tres-artigos-com-corte-065.md) (até 3 artigos, corte 0,65), [ADR-0015](0015-recuperacao-semantica-do-regulamento.md)

## Contexto

O cenário `Pergunta cuja resposta exige dois artigos recupera os dois` existe
desde o ADR-0016 e descreve um caso real do documento:

> O **Art. 39** (Cap. VI, salão) manda *"respeitar o período de silêncio
> previsto no Capítulo III"* e **não dá o horário**. Quem dá é o **Art. 16**
> (Cap. III): *"entre 22h e 8h"*. Nenhum dos dois responde sozinho.

Implementada a busca do ADR-0021, o cenário ficou **vermelho**. A pergunta
*"posso fazer festa com som no salão até 2h"* devolveu:

| | artigo | capítulo | similaridade |
|---|---|---|---|
| 1 | Art. 39 | VI — salão | 0,7545 |
| 2 | Art. 17 | III — silêncio | 0,7367 |
| 3 | Art. 37 | VI — salão | 0,7100 |

O Art. 16 **não aparece nem no top 8** — ele fica abaixo de 0,698, atrás de
seis artigos do Capítulo VI.

**A causa é a decisão do ADR-0016.** O título do capítulo entra no texto que
gera o vetor, e isso é o que faz *"até que horas a piscina funciona"* achar o
Art. 22. O efeito colateral é que **todos os 8 artigos do "Capítulo VI: Salão
de festas, churrasqueira e quadra" casam com qualquer pergunta que diga
'salão'** — e empurram para baixo o artigo de outro capítulo que tem a
resposta. A mesma decisão que faz a piscina funcionar enterra o Art. 16.

Aumentar o limite de 3 não resolve: o Art. 16 não está no top 8. Baixar o corte
não resolve: o problema é **ordem**, não limiar.

## A medição

O Art. 39 **cita o Capítulo III por escrito**. Isso é um sinal mecânico, que
está no texto e não depende de modelo. Medi quatro formas de usá-lo — todas
restringindo a busca ao Capítulo III — e elas se separam claramente:

| Consulta usada | 1º colocado | Margem sobre o 2º |
|---|---|---|
| a pergunta do morador | Art. 17 ❌ | — |
| o texto inteiro do Art. 39 | Art. 16 ✅ | 0,0018 — ruído |
| a frase da remissão, escrita à mão | Art. 16 ✅ | 0,0394 |
| **a frase da remissão extraída pelo código** | **Art. 16 ✅ 0,8114** | **0,0127** |

A pergunta do morador erra: ela fala de "festa", e o Art. 17 é sobre festas
dentro das unidades. O artigo inteiro acerta por margem de ruído. **A frase que
contém a remissão acerta porque ela nomeia o conceito** — *"o período de
silêncio previsto no Capítulo III"* —, e o Art. 16 é o artigo que **define**
esse conceito.

E o alcance é pequeno: **3 dos 96 artigos** citam outro capítulo.

| Artigo | Remete a | Sobre |
|---|---|---|
| Art. 39 (Cap. VI) | Cap. III | o horário do período de silêncio |
| Art. 43 (Cap. VI) | Cap. XIII | as penalidades por dano |
| Art. 66 (Cap. IX) | Cap. XII | o descarte de item volumoso |

Os três são casos legítimos de *"a resposta continua lá"*.

## Decisão

Depois da busca principal, a recuperação **segue a remissão de capítulo do
artigo melhor colocado que tiver uma**:

1. acha a primeira frase daquele artigo que cite `Capítulo <romano>` de um
   capítulo **diferente** do dele;
2. usa **essa frase** como consulta, restrita àquele capítulo;
3. traz o **melhor** artigo de lá, se ele passar do mesmo corte de **0,65**.

O artigo trazido pela remissão **ocupa a última vaga** das três do ADR-0021 —
o total nunca passa de 3. **No máximo uma remissão é seguida por busca**, a do
artigo melhor colocado.

## Alternativas consideradas

- **Aumentar o limite de 3 artigos.** Rejeitada **pela medição**, não por
  preferência: o Art. 16 não está no top 8. Teria que ir a 9 artigos, o que
  devolve meio capítulo e colide com a Garantia 4.
- **Não embutir o título do capítulo no vetor** (desfazer parte do ADR-0016).
  Resolveria o efeito de aglomeração do Capítulo VI. Rejeitada porque quebra o
  caso que motivou aquela decisão: *"Art. 22. A piscina observa os seguintes
  períodos de uso"* sozinho não diz de que coisa fala, e o vetor dele fica
  ambíguo entre piscina, academia e salão.
- **Expandir a consulta com uma segunda pergunta gerada pelo modelo.**
  Rejeitada por princípio deste projeto: a qualidade da recuperação passaria a
  depender do que o modelo decide escrever, e regra que mora no prompt não
  conta. A remissão, ao contrário, está escrita no documento.
- **Mudar o cenário para aceitar o que a busca devolve.** Rejeitada porque é
  testar o que foi construído em vez do que foi decidido. O cenário descreve um
  fato do documento — nenhum dos dois artigos responde sozinho — e esse fato não
  mudou. Além disso, remover cenário exige ADR próprio (regra 2 do `CLAUDE.md`).
- **Usar o texto inteiro do artigo como consulta da remissão.** Funciona, e foi
  medido: Art. 16 em 1º. Rejeitada pela **margem**: 0,0018 sobre o 2º colocado é
  ruído, e uma decisão que depende de 0,2% de diferença não é uma decisão, é
  sorte. A frase da remissão dá 0,0127, sete vezes mais.

## Consequências

**O que fica mais fácil:** a resposta a uma pergunta cuja regra está dividida
entre dois capítulos passa a trazer os dois artigos, e o morador recebe o
horário em vez de *"respeite o período de silêncio"*.

**O que fica mais difícil, ou passa a custar atenção:** a busca passa a fazer
**duas** chamadas ao modelo de embedding quando o artigo melhor colocado tem
remissão, em vez de uma. Só 3 dos 96 artigos têm, então na prática isso é raro;
mas a conta de quota do spike 2.4 ganha essa linha.

E há uma dependência nova sobre o **formato do documento**: a extração procura
a string `Capítulo <romano>`. Se uma edição futura do regulamento escrever
"cap. III" ou "no capítulo terceiro", a remissão deixa de ser achada — em
silêncio, sem erro. O cenário é a única rede.

**Risco aceito:** a frase extraída é a **primeira** do artigo que cita outro
capítulo. Um artigo que citasse dois capítulos em frases diferentes teria só a
primeira seguida. Nenhum dos três casos do documento é assim; se um dia for, o
cenário que falhar vai dizer.

**O que esta decisão NÃO faz:** ela não segue remissão a **artigo**
(*"conforme o Art. 12"*), só a capítulo. Não há caso disso no documento — e
inventar o mecanismo sem um caso que o exija seria construir no escuro.

## Verificação

| Cenário | Protege | Tipo |
|---|---|---|
| Pergunta cuja resposta exige dois artigos recupera os dois | a decisão deste ADR | positivo — é o cenário que a motivou |
| A dúvida da piscina aos domingos recupera o trecho que a responde | que a remissão não estrague o caso simples | **regressão** |
| O recorte nunca devolve o regulamento inteiro | `I-05` — o teto de 3 continua valendo **com** a remissão | **regressão** |
| O recorte da piscina não arrasta capítulos de outros assuntos | Garantia 4 | **regressão** |

Arquivo: `tests/features/regulamento.feature`

## Onde isso vive no código

| O quê | Onde |
|---|---|
| Achar a remissão e extrair a frase | `app/infra/recuperacao.py` → `remissao_de_capitulo` |
| Seguir a remissão e trazer o artigo | `app/infra/recuperacao.py` → `RecuperadorDeRegulamento.buscar` |
| O teto de 3, com a vaga da remissão | `app/infra/recuperacao.py` → `MAXIMO_DE_ARTIGOS` |

⚠️ A busca restrita ao capítulo usa `capitulo LIKE 'Capítulo <romano>:%'`, e o
`:` no padrão não é enfeite: sem ele, `Capítulo VI` casaria com
`Capítulo VIII`. É o mesmo bug de prefixo que derrubou um cenário durante esta
implementação — numeral romano não se compara por prefixo.
