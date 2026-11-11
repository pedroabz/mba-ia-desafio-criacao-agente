---
name: execute-plan
description: "Executar um plano de implementação já validado pelo usuário, passo a passo, fazendo os cenários de cada passo ficarem verdes. Use SEMPRE que o pedido for construir a partir de um plano aprovado: 'executa o plano', 'pode implementar o plano', 'roda o plano 1.1', 'aprovei, pode seguir', 'faz o passo P2', 'implementa o que está no plano'. Também em inglês: 'execute the plan', 'run the approved plan', 'implement step P1'. A skill recusa-se a rodar sobre plano não validado e a decidir qualquer coisa: se faltar escolha, ela para e devolve como decisão pendente."
---

# Executar um plano validado

Pegar um plano **já aprovado pelo usuário** e construí-lo passo a passo, até os cenários de cada passo ficarem verdes.

```
generate-spike  →  usuário decide  →  consolidate-spike  →  usuário valida  →  execute-plan
```

Duas regras organizam tudo, e as duas são recusas:

1. **Você não roda sobre plano não validado.**
2. **Você constrói o que foi decidido; não decide.**

## O gate de validação é a primeira coisa a conferir

Antes de qualquer outra leitura, abra o plano e confira o campo `Status`.

- **`validado`** — pode executar.
- **`rascunho`** — **pare.** Diga ao usuário que o plano aguarda revisão, mostre onde ele está e o que ele propõe. Não execute "a parte óbvia enquanto isso".

Isso parece formalidade e não é. Um plano em rascunho é uma proposta que ninguém leu inteira; executá-lo transforma a validação em narração do que já foi feito, que é o mesmo que não ter validação. E quem aprova depois está aprovando código, não plano — o custo de discordar já ficou alto demais para ser exercido.

Se o usuário pedir explicitamente para executar um plano em rascunho, **essa é a validação** — registre o campo como validado, com a data, antes de começar.

## Por que a recusa de decidir é a parte importante

É tentador, no meio de um arquivo, resolver uma pequena ambiguidade e seguir. O problema não é a escolha em si — frequentemente ela é boa. O problema é que ela fica **invisível**: sem ADR, sem alternativa registrada, sem cenário. Meses depois alguém encontra o comportamento e não tem como saber se foi pensado ou se foi acidente, nem o que estava em jogo para poder mudá-lo.

Decisão tomada em silêncio dentro de uma implementação é a perda que esta cadeia de skills inteira existe para impedir. Parar custa cinco minutos; descobrir depois custa a confiança no registro todo.

## Antes de escrever código

1. **Leia o plano inteiro**, não só o passo da vez. A ordem existe por um motivo, e o passo seguinte costuma explicar por que o atual é como é.
2. **Leia o ADR de origem do passo por completo** — não só o campo *Decisão*. As seções *Consequências* e *Alternativas consideradas* dizem o que **não** fazer, e é ali que mora a armadilha: a implementação óbvia costuma ser exatamente a alternativa que foi rejeitada.
3. **Leia os cenários** que o passo precisa deixar verdes. Eles são a especificação executável; o ADR é o porquê.
4. **Leia o `CLAUDE.md`** do projeto, se houver — é onde ficam as armadilhas já pagas.
5. **Confirme que as dependências do passo já foram executadas.** Se o plano diz `Depende de: P2` e o P2 não está feito, a ordem está errada ou o plano está desatualizado: reporte em vez de contornar.

## Durante

**Um passo por vez, na ordem do plano.** Mesmo que o passo vizinho seja fácil e esteja ali do lado. Cada passo tem critério de pronto próprio; misturar dois faz um esconder a falha do outro.

**Deixe o rastro no código.** Quando uma linha existe por causa de uma decisão, cite o identificador no comentário — `ADR-0001`, `I-06`. Quem ler depois chega à decisão sem adivinhar, e quem for alterar descobre que há algo em jogo antes de mexer.

Isso vale em dobro para o que parece arbitrário ou errado à primeira vista. Um índice parcial, uma mensagem de erro deliberadamente vaga, um filtro repetido — tudo isso parece descuido para quem não conhece a razão, e será "corrigido" por alguém de boa-fé. O comentário é o que impede.

**As regras duras pertencem à camada que as impõe, não ao código que chama.** Se um invariante pode ser garantido pelo banco, pelo tipo ou pela assinatura, é lá que ele vai — não num `if` que alguém remove. Verificar antes de gravar não é o mesmo que o banco recusar a gravação: entre a verificação e a gravação cabe outra requisição.

## Ao terminar cada passo

1. **Rode os cenários do passo.** Verdes é o critério; "o código roda" não é.
2. **Rode a suíte inteira.** Passo novo que quebra cenário antigo é regressão, não progresso.
3. **Tire a etiqueta `@pendente`** dos cenários que agora passam — e só desses.
4. **Preencha *Onde isso vive no código*** no ADR correspondente: arquivo e símbolo. É a única seção de um ADR aceito que se edita, e é o que alimenta a parte do README que precisa apontar código.
5. **Marque o passo no plano.**
6. **Rode a verificação de coerência** do projeto, se houver (`scripts/cobertura.py`).

## Ao terminar o plano: confira o conjunto declarado

O plano declara, na seção *Cenários que este plano faz virar*, o conjunto completo de cenários que devem passar de vermelho a verde. Antes de marcar o plano como executado, **compare o conjunto real com o declarado** — rode a suíte e veja quais mudaram de cor.

Os dois desvios possíveis significam coisas diferentes, e nenhum é detalhe:

**Faltou virar.** Um cenário declarado continua vermelho. Ou um passo não fez o que prometia, ou o cenário exige mais do que o plano supôs. Nos dois casos o plano **não está executado** — investigue e reporte antes de declarar qualquer coisa.

**Virou sem estar na lista.** Um cenário que o plano não prometia ficou verde. Duas causas, e a segunda é pior:
- um passo fez mais do que o planejado — escopo que ninguém aprovou, e que precisa voltar ao usuário;
- o cenário era mais fraco do que se pensava e já passaria por outro motivo. Isso significa que ele **não estava protegendo o que se imaginava**, e vale reescrevê-lo. Um cenário que fica verde sem que ninguém tenha implementado a coisa que ele deveria cobrar é confiança falsa.

Se o plano não trouxer essa seção — planos escritos antes desta disciplina existir —, monte o conjunto a partir dos critérios de pronto dos passos e diga que fez isso.

## Prove que o teste pega

Antes de declarar pronto um cenário de **regressão**, sabote de propósito a decisão que ele protege e confirme que **ele** falha — de preferência só ele. Depois restaure.

Leva trinta segundos e separa teste que protege de teste que acompanha. Um cenário de regressão que continua verde com a decisão invertida é pior que nenhum: dá confiança falsa exatamente onde você mais precisa de confiança real.

## Quando parar

Pare e devolva ao usuário quando:

- o plano não estiver validado;
- faltar uma escolha que nenhum ADR fixou;
- o cenário não for satisfazível como está escrito — isso costuma significar que a decisão tem um problema, não o teste;
- a implementação exigir contrariar uma restrição derivada ou um invariante;
- o plano revelar-se incompleto ou fora de ordem.

Nos cinco casos, **o que você encontrou é o entregável**. Um bloqueio bem descrito vale mais que uma implementação que o contornou em silêncio.

## Regras

- **Não execute plano em `rascunho`.**
- **Nunca decida.** Escolha não fixada volta como decisão pendente.
- **Um passo por vez, na ordem do plano.**
- **Nunca amplie o escopo do plano.** Trabalho que não está nele volta como proposta de passo novo, para o usuário validar.
- **Não declare o plano executado sem conferir o conjunto de cenários.** Cenário declarado que ficou vermelho, ou cenário verde que ninguém prometeu, são as duas formas de o plano ter saído do trilho sem ninguém notar.
- **Critério de pronto é cenário verde**, sempre.
- **Nunca apague cenário** nem troque `@pendente` por `@skip`. Teste pulado é invisível, e invisível é perdido.
- **Cite o identificador da decisão** no comentário de todo trecho que existe por causa dela.
- **Nunca escreva em dados de referência imutáveis** do projeto.
- Relate honestamente o que não ficou verde e por quê — implementação parcial bem descrita é informação; implementação parcial silenciosa é dívida.
