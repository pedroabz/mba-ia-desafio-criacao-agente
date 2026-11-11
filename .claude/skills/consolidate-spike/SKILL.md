---
name: consolidate-spike
description: "Coordenar o que sai de um spike cujas decisões já foram tomadas: triar cada resultado entre ADR, cenário de teste, trabalho pronto e trabalho bloqueado, e então invocar generate-adr, generate-bdd e generate-plan para materializar cada parte. É a ponte entre decidir e construir. Use SEMPRE que o usuário terminar de decidir as pendências de um spike: 'consolida o spike', 'o que faço agora com essas decisões', 'já decidi tudo, e agora', 'o que dá para implementar disso', 'tria isso aí', 'fecha o spike 1.1', 'transforma o spike em trabalho'. Também em inglês: 'consolidate the spike', 'what can we build from this', 'triage these decisions'. Não decide, não escreve os artefatos por conta própria e não implementa nada — o plano que ela encomenda nasce em rascunho e só vira código depois que o usuário valida."
---

# Consolidar um spike

Pegar um spike com as decisões preenchidas e transformá-lo em **trabalho classificado**: o que vira registro permanente, o que vira teste, o que dá para construir agora e o que está travado — sem deixar nada escapar entre as categorias.

A regra que organiza tudo: **você tria e planeja; não decide e não constrói.** Decidir é do usuário (`generate-spike`); construir é da skill `execute-plan`, e só depois que o usuário validar o plano que esta aqui produz.

```
generate-spike  →  usuário decide  →  consolidate-spike  →  usuário valida  →  execute-plan
   investiga                          tria e invoca:                             constrói
                                      generate-adr
                                      generate-bdd
                                      generate-plan
```

Esta skill é **coordenador**: ela não escreve ADR, não escreve cenário e não escreve plano. Ela decide **o que vira o quê** e chama a skill de cada artefato. O trabalho próprio dela é a triagem — e a auditoria das restrições que não cabem em nenhum dos três.

**Nada é implementado a partir de um spike.** O caminho do spike até o código passa obrigatoriamente por um plano aprovado.

## Por que este passo existe

Sem ele, a triagem acontece **na cabeça de quem estiver rodando no momento**, e muda a cada vez. Um spike vira três ADRs numa sessão e cinco na outra; um cenário vai para `@storage` aqui e `@conversa` ali; o trabalho que já dava para fazer fica esperando porque ninguém percebeu que não dependia de nada. A inconsistência não aparece de imediato — ela aparece semanas depois, como uma decisão que nunca chegou ao código.

Há também um motivo que só fica visível quando se tenta responder "isso dá para implementar?": **prontidão não é propriedade de uma decisão isolada.** Ela depende do grafo — do que mais já foi decidido, e do que ainda está pendente em *outros* spikes. Nenhum ADR sabe responder isso sozinho; é preciso olhar o conjunto. Esse olhar é este passo.

## Entrada

Um documento de spike com os campos `**Decisão:**` preenchidos. Se algum ainda estiver `_[pendente]_`, ele **não** entra na triagem — e aparece no relatório, porque pendência omitida é indistinguível de pendência esquecida.

Leia também, antes de triar:

- os **outros** documentos de spike, em especial os que têm decisões pendentes: eles são a fonte dos bloqueios;
- `docs/adr/` — para não registrar de novo o que já tem ADR, e para enxergar dependências entre decisões;
- o plano (`TODO.md`) — é onde a fila será escrita.

## A triagem: dois eixos, não quatro baldes

A tentação é criar quatro categorias exclusivas. Não funciona: uma decisão costuma virar ADR **e** cenário **e** estar pronta para implementar. São dois eixos independentes.

### Eixo 1 — registro: o que este resultado vira?

| Vira | Quando | Skill |
|---|---|---|
| **ADR** | é escolha estratégica entre alternativas reais | `generate-adr` |
| **Cenário** | tem comportamento observável a amarrar | `generate-bdd` |
| **Nenhum dos dois** | é consequência mecânica de outra decisão, ou a convenção do stack resolve | — |

Não reimplemente os critérios: as duas skills já os definem. **Invoque-as**, não substitua.

### Eixo 2 — prontidão: dá para construir agora?

| Estado | Significa |
|---|---|
| **Pronto** | toda decisão de que depende já foi tomada |
| **Bloqueado por `<spike/decisão>`** | depende de algo que ninguém decidiu ainda |

O teste prático, e ele é mais confiável que a intuição:

> **Se para implementar você precisaria escolher alguma coisa, não está pronto.**

Escolher durante a implementação é decidir sem registrar — exatamente o que esta cadeia de skills existe para impedir. Quando isso acontecer, pare e **devolva como decisão nova**, para o usuário resolver. Não escolha "o caminho óbvio" e siga.

Repare que prontidão é **por fatia de trabalho**, não por decisão inteira. É comum uma decisão ter uma parte pronta e outra travada — o schema de uma tabela pode estar determinado enquanto a ligação dela com o resto da aplicação depende de um spike aberto. Quebre nesse ponto em vez de bloquear tudo: adiar o que já dá para fazer custa tanto quanto construir o que não dá.

## As restrições que não viram ADR — o buraco a vigiar

Spike produz dois tipos de resultado, e só um deles tem casa:

- **Decisões** — escolhas entre alternativas. Viram ADR. ✅
- **Restrições derivadas** — consequências que o enunciado, a biblioteca ou a realidade impõem, sem escolha nenhuma. *"Tool que exige confirmação não pode viver dentro de um wrapper que descarta a sessão"* não é preferência: é como a biblioteca funciona.

Restrição **não vira ADR** (não há alternativa a registrar) e muitas vezes **não vira cenário** (não há comportamento a observar até o sistema existir). Resultado: ela fica em prosa, num documento, protegida por nada.

Então a consolidação tem uma obrigação a mais: para cada restrição derivada, dizer **o que a protege**. As camadas, da mais forte à mais fraca:

1. **o código impede** — índice do banco, tipo, assinatura;
2. **um teste falha** — cenário de regressão;
3. **um script acusa** — verificação de coerência que sai com erro;
4. **um documento avisa** — `CLAUDE.md`, ADR, spike.

Quando uma restrição estiver só no nível 4, **proponha como subi-la**. Frequentemente dá: uma restrição sobre estrutura de código vira uma verificação que varre os arquivos e falha. Vinte linhas de script valem mais que três parágrafos que ninguém relê.

## A saída é um plano, e ele passa por validação

Esta skill **não produz trabalho pronto para começar**, e **não escreve o plano por conta própria**: ela invoca `generate-plan`, passando o que a triagem apurou — quais ADRs serão implementados, o que está pronto, o que está bloqueado e por quê.

A divisão importa. O formato do plano, a granularidade dos passos e o ciclo de vida do status são assunto da `generate-plan`, que também serve para planejar trabalho que **não** veio de spike nenhum (um refactor, uma dívida, uma correção). Reimplementar o formato aqui criaria duas definições do mesmo artefato, que divergem na primeira vez que uma das duas for ajustada.

O que você entrega a ela é a matéria-prima que só a triagem conhece:

| O que passar | Vem de |
|---|---|
| ADRs a implementar | eixo 1 |
| O que está pronto | eixo 2 |
| O que está bloqueado, e por quê | eixo 2 |
| Cenários que cada fatia deve deixar verde | `generate-bdd` |
| Restrições sem proteção mecânica | seção das restrições |

O plano nasce `rascunho`. **Você não o valida** — quem valida é o usuário.

## Ordem de trabalho

1. Varra as decisões preenchidas e monte a triagem nos dois eixos. **Mostre a tabela ao usuário antes de gerar qualquer coisa** — é barato corrigir uma classificação errada agora e caro depois de cinco arquivos criados.
2. Invoque `generate-adr` para o que vira ADR.
3. Invoque `generate-bdd` para o que vira cenário. Tudo nasce `@pendente`.
4. Classifique a prontidão de cada fatia de trabalho.
5. Invoque `generate-plan` com o resultado da triagem.
6. Levante as restrições derivadas e diga o que protege cada uma.
7. Relate — e **termine pedindo a validação do plano**, deixando claro que nada será construído antes disso.

## Regras

- **Nunca decida nada.** Se a triagem revelar uma escolha não feita, ela volta como decisão pendente, não como palpite.
- **Nunca implemente aqui.** Esta skill termina com um plano em `rascunho`. Construir é `execute-plan`, depois da validação.
- **O plano nasce `rascunho`.** Você não o marca como validado — quem valida é o usuário. Skill que aprova o próprio plano não tem gate nenhum.
- **Não reimplemente nada que as skills de artefato já fazem** — nem os critérios de ADR, nem os de cenário, nem o formato do plano. Invoque `generate-adr`, `generate-bdd` e `generate-plan`. Definição duplicada diverge na primeira vez que uma das cópias é ajustada, e aí as duas ficam erradas de formas diferentes.
- **Pendência aparece no relatório.** Decisão que ficou de fora e por quê.
- **Toda restrição derivada recebe uma linha dizendo o que a protege.** Quando a resposta for "nada", isso é um achado, não um detalhe.
- Passo sem critério de pronto verificável não entra no plano.

## Relatório

Ao terminar, diga em poucas linhas:

- a tabela de triagem — cada resultado e para onde foi;
- quantos ADRs e cenários saíram;
- o plano: quantos passos, quanto ficou de fora e por quê;
- as restrições derivadas e o nível de proteção de cada uma, **nomeando as que estão desprotegidas**;
- o que ficou pendente e por quê;
- **o pedido de validação**, com o caminho do plano.
