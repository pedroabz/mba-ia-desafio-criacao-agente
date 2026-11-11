---
name: generate-plan
description: "Escrever um plano de implementação revisável a partir de decisões já tomadas — passos ordenados, com dependências, entregas e critério de pronto verificável. O plano nasce em rascunho e só vira trabalho depois que o usuário o valida. Use SEMPRE que for preciso transformar decisão em trabalho antes de codar: 'monta o plano', 'gera o plano de implementação', 'como vamos construir isso', 'planeja a implementação do ADR-0002', 'faz um plano para isso', 'quebra isso em passos'. Também em inglês: 'generate the implementation plan', 'plan this work', 'break this into steps'. Não implementa nada — isso é da skill execute-plan, e só depois da validação."
---

# Escrever um plano de implementação

Transformar decisões já tomadas em **trabalho ordenado e revisável**: passos com dependências, entregas e critério de pronto que alguém consegue conferir sem opinar.

A regra que organiza tudo: **você planeja; não decide e não constrói.** O plano nasce `rascunho`, e quem o aprova é o usuário.

```
decisões tomadas  →  generate-plan  →  usuário valida  →  execute-plan
```

## Por que o plano é um artefato, e não uma lista de tarefas

Uma lista de tarefas é lida item a item, e quem a executa nunca vê a forma do trabalho inteiro: a ordem, o que ficou de fora, onde o escopo cresceu além do que foi decidido. É no todo que se percebe que falta um passo, que dois poderiam ser um, ou que o terceiro depende de algo que ninguém decidiu.

E o plano existe para ser **recusável**. Se ele chega depois que o código já está escrito, a revisão vira narração: quem lê está aprovando trabalho feito, não proposta — e o custo de discordar já é alto demais para ser exercido. Por isso o plano vem antes, inteiro, e com um campo que precisa ser preenchido por uma pessoa.

## De onde vem o escopo

1. **Um ou mais ADRs** — o caso comum: decisões registradas que ainda não viraram código.
2. **Um resultado de triagem** (`consolidate-spike`) — já vem com prontidão classificada.
3. **Um pedido direto** — um refactor, uma correção, uma dívida. Também vale, desde que não dependa de escolha não feita.

Em todos os casos, leia antes: os ADRs envolvidos **por completo** (as seções *Consequências* e *Alternativas consideradas* mudam o desenho dos passos), os cenários existentes, e o estado atual do código — planejar sobre o que você supõe que existe é a forma mais comum de plano nascer errado.

## O teste que decide se algo entra no plano

> **Se para implementar seria preciso escolher alguma coisa, não entra.**

Escolher durante a implementação é decidir sem registrar — e a decisão fica invisível, sem ADR e sem alternativa anotada. Quando encontrar um desses, **devolva como decisão pendente**, não como passo. Um plano que embute escolhas não revisadas é pior que nenhum, porque parece aprovado.

Corolário: **trabalho bloqueado não vira passo.** Vira linha na seção *O que fica de fora*, com o que o destrava.

## Planeje a partir do estado final, não do diff

O erro mais caro ao escrever um plano é planejar **o que falta escrever** em vez de **o que precisa passar a existir**. São coisas diferentes, e a diferença é invisível para quem acabou de mexer no código: com os arquivos frescos na cabeça, a lacuna parece ser sempre "falta ligar as pontas".

O que escapa por esse buraco é tudo que **não corresponde a um arquivo novo**: o banco que precisa existir, o schema que precisa ser aplicado, o diretório que precisa ser criado, o serviço que precisa subir, a variável que precisa estar no ambiente. Nada disso aparece num diff mental, e por isso nenhum passo é escrito para elas — até a implementação travar no primeiro comando.

O método que evita isso é descrever o alvo antes dos passos:

1. **Escreva o estado final em uma frase**, em termos do que o sistema faz, não de arquivos: *"a API responde a partir de um banco que sobrevive ao reinício"*.
2. **Liste o que precisa existir para essa frase ser verdadeira** — código, dados, infraestrutura, configuração, processo. Tudo, mesmo o que parece óbvio.
3. **Marque o que já existe e está em uso.** Não o que está escrito: o que está **em uso**. Código testado mas nunca executado fora de teste conta como ausente.
4. **O resto é o plano.**

O passo 3 é onde se erra. Peça a prova: qual comando, hoje, demonstra que isso existe? Se a única prova é um teste rodando contra um recurso temporário, o recurso **não existe** no sistema — existe no teste.

E quando um passo depender de algo que nenhum passo anterior cria, isso não é detalhe de implementação a resolver na hora: **é um passo faltando**.

## Granularidade: onde cortar um passo

A pergunta certa não é "quão grande" e sim: **um passo termina onde o sistema volta a ficar coerente e verificável.**

- Fino demais ("criar o arquivo", "adicionar o import") vira cerimônia, e o critério de pronto some — não dá para escrever um cenário para "criar arquivo".
- Grosso demais ("implementar o módulo") esconde onde falhou: o passo fica vermelho e ninguém sabe qual parte quebrou.

Dois sinais práticos de que o corte está certo:

- o passo tem **pelo menos um cenário** que fica verde quando ele termina;
- se você parar o trabalho ali, o repositório continua num estado que faz sentido.

Quando um passo precisa de três critérios de pronto não relacionados, provavelmente são três passos. Quando dois passos sempre ficariam verdes juntos, provavelmente são um.

**Prefira fatiar por garantia, não por arquivo.** "A unicidade do código passa a ser imposta pelo banco" é um passo; "escrever `banco.py`" não é — ele atravessa várias garantias e não tem como ficar verde pela metade.

## Formato

Salve em `docs/plano-<id>-<slug>.md`. Quando o plano nasce de um spike, use o **mesmo `<id>` do spike** — o pareamento com `docs/spike-<id>-<slug>.md` torna óbvio de onde ele veio.

```markdown
# Plano: <o que será construído, em uma linha>

**Status:** rascunho
**Origem:** <ADRs, spike, ou o pedido que o motivou>
**Implementa:** ADR-NNNN, ADR-NNNN

## O que este plano constrói

<Dois ou três parágrafos, para quem não estava na conversa: o que passa a
existir quando ele terminar, e por que isso importa. Quem lê para aprovar
precisa entender o alvo sem abrir outros arquivos.>

## O que fica de fora

<Cada item que poderia parecer incluído e não está, com o motivo — e, se
estiver bloqueado, o que o destrava. Escopo não dito volta como surpresa,
e surpresa no meio da implementação custa a validação inteira.>

## Passos

### P1 — <título em voz ativa>

**Implementa:** ADR-NNNN (ou: o pedido)
**Depende de:** — (ou P<n>)
**Entrega:** <arquivos e símbolos que passam a existir ou mudam>
**Pronto quando:** os cenários <nomes> ficam verdes
**Risco:** <o que pode dar errado, ou "—">

### P2 — <título>
...

## Ordem e paralelismo

<O que precisa ser sequencial, e por quê. O que pode ir junto. Se tudo é
sequencial, diga — é informação.>

## Riscos do plano

<O que pode invalidar o plano como um todo: uma decisão que pode mudar, uma
biblioteca não verificada, uma dependência externa.>

## Validação

- [ ] Revisado e aprovado — _data:_
```

## Critério de pronto

**Sempre um cenário ficando verde.** Nunca "o código funciona", nunca "a rota responde", nunca "testei manualmente". Critério que depende de alguém olhar e achar que está bom não é critério — ele não falha sozinho, e portanto não protege nada.

**Passo sem cenário que o verifique não entra no plano.** Se o trabalho é real e não existe cenário, o que falta é cenário: pare e gere-o (`generate-bdd`) antes de planejar. Essa ordem importa — cenário escrito depois do código tende a testar o que foi construído em vez do que foi decidido.

## O conjunto de cenários que o plano faz virar

Critério por passo não basta. É possível cumprir todos os passos, cada um com o seu cenário verde, e ainda assim deixar vermelho um cenário que aquele trabalho deveria ter resolvido — porque ninguém somou.

Por isso o plano declara, **no nível do plano**, o conjunto completo de cenários que passam de vermelho a verde quando ele terminar. É um contrato verificável: no fim, ou o conjunto bate, ou algo saiu do previsto nos dois sentidos possíveis.

**Como montar o conjunto.** Para cada ADR que o plano implementa, abra a tabela *Verificação* dele e liste os cenários. Cada um precisa cair em exatamente uma destas caixas:

1. **Fica verde** — está no critério de pronto de algum passo.
2. **Continua vermelho**, com o motivo e o que o destrava.

Cenário que não cai em nenhuma das duas é **buraco no plano**: ou falta um passo, ou falta dizer por que ele fica de fora. Essa é a conferência; ela é barata e pega omissão que a leitura passo a passo não pega.

```markdown
## Cenários que este plano faz virar

| Cenário | Passo | Arquivo |
|---|---|---|
| <nome> | P1 | `tests/features/<tema>.feature` |

**Continuam vermelhos**, e por quê:

| Cenário | Por quê | Destrava com |
|---|---|---|
| <nome> | depende do agente respondendo | Fase 4 + `.env` |
```

**Os dois desvios, no fim da execução, significam coisas diferentes:**

- **Faltou virar** — o passo não fez o que prometia, ou o cenário exige mais do que o plano supôs. Investigar antes de declarar o plano executado.
- **Virou sem estar na lista** — ou um passo fez mais do que o planejado (escopo que ninguém aprovou), ou o cenário era mais fraco do que se pensava e já passava por outro motivo. O segundo caso é o pior: significa que aquele cenário não estava protegendo o que se imaginava.

Um plano cujo conjunto é **vazio** — nenhum cenário muda de cor — é um sinal, não necessariamente um erro. Trabalho de pura reorganização existe. Mas vale perguntar em voz alta o que exatamente passa a ser verdade depois dele, e como alguém saberia.

## Ciclo de vida

| Status | Significa |
|---|---|
| `rascunho` | escrito, aguardando revisão. **Nenhuma linha de código foi escrita.** |
| `validado` | aprovado pelo usuário, com data. `execute-plan` pode rodar. |
| `executado` | todos os passos concluídos, com data. |

**Você nunca marca um plano como validado.** Quem valida é o usuário. Skill que aprova o próprio plano não tem gate nenhum — é só uma etapa a mais antes de fazer o que ia fazer de qualquer jeito.

**Revisão depois do feedback:** edite o plano em `rascunho` e peça validação de novo. Depois de `validado`, mudança de escopo não é edição silenciosa — ou é um plano novo, ou é um passo acrescentado que volta para aprovação.

## Regras

- **Nunca decida.** Escolha não fixada por ADR vira decisão pendente, não passo.
- **Nunca implemente.** Esta skill termina com o arquivo escrito.
- **Nunca marque como validado.**
- **Todo passo tem critério de pronto verificável.** Sem isso, não entra.
- **Confira a cadeia de dependências antes de emitir.** Para cada passo, pergunte: tudo de que ele precisa é criado por um passo anterior, ou já existe **em uso**? Passo que consome algo que ninguém cria é plano quebrado, e o erro é fácil de não ver quando a ordem parece razoável.
- **Todo cenário dos ADRs implementados tem destino declarado** — ou vira verde em algum passo, ou é listado como continuando vermelho, com motivo. Sem terceira opção: cenário sem destino é omissão que a leitura passo a passo não detecta.
- **Diga o que fica de fora.** Omissão lida como esquecimento é indistinguível de omissão lida como escopo.
- Escreva para quem não estava na conversa — vale a mesma disciplina da `generate-spike`: quem abre o plano para aprovar não tem o contexto que você tem agora.
- **Não confunda código escrito com capacidade existente.** É o erro mais comum ao descrever o ponto de partida: *"já temos um repositório SQLite completo e testado"* dá a entender que existe um banco, quando o que existe é código que nunca rodou fora de teste. Quem lê para aprovar decide com base nesse parágrafo — se ele superestima o que está de pé, o plano parece menor do que é. Diga o que **existe em execução** e o que existe **apenas como código**, separadamente, e evite adjetivos como "completo" e "pronto" para descrever código não integrado.

## Saída

- `docs/plano-<id>-<slug>.md`, em `rascunho`.
- Um ponteiro no `TODO.md` — só o link e o estado, **nunca a lista de passos**. Duplicar os passos em dois lugares garante que um fique desatualizado.

Ao terminar, diga: quantos passos, o que ficou de fora e por quê, quais decisões pendentes apareceram no caminho, e **peça a validação** — deixando claro que nada será construído antes dela.
