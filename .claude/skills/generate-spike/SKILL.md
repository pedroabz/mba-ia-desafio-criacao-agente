---
name: generate-spike
description: "Investigar uma incerteza técnica e produzir um documento de decisões que desbloqueia a tarefa. Use sempre que for preciso explorar alternativas, entender trade-offs, provar que algo funciona antes de implementar, ou definir caminhos técnicos. Frases de gatilho: 'roda um spike', 'investiga antes de implementar', 'quais as opções para X', 'preciso decidir entre A e B', 'prova de conceito', 'POC', 'descobrir como fazer Y nesta lib', 'validar a abordagem', 'derrubar risco técnico', 'não sei se dá pra fazer assim', ou qualquer menção a explorar alternativas e trade-offs antes de planejar ou codar. Use também quando o pedido incluir overview de comportamento, cenários BDD ou diagrama de arquitetura junto da investigação."
---

# Spike

Investigar uma incerteza técnica e entregar um **documento de decisões**: o que foi descoberto, o que isso elimina, e quais escolhas restam — com opções, trade-offs e recomendação. O usuário lê, decide, e o documento vira a base da implementação.

O código do spike é descartável. **O documento é o produto.**

A regra que organiza tudo: você **investiga e recomenda**; o usuário **decide**. Um spike que já escolheu por conta própria não desbloqueia — ele só esconde a escolha dentro de uma implementação.

## Quando o spike se justifica

Nem toda dúvida merece documento. Faça a triagem:

- Existe **mais de um caminho razoável** com o stack do projeto?
- Existe **dúvida real** sobre qual seguir, com consequências diferentes?
- A resposta **bloqueia** decisões seguintes (arquitetura, schema, contrato)?
- A documentação é insuficiente, desatualizada, ou conflita com o que está instalado?

Se a resposta for não para todas, diga ao usuário que não há alternativa significativa a pesquisar — a resposta é direta e não justifica um documento. Economize o tempo dele.

## De onde vem o escopo

O usuário define o escopo de uma destas formas:

1. **Item de plano** — aponta uma fase ou tarefa de um `TODO.md`/plano do projeto. Leia esse item e **enumere os bullets dele literalmente**: eles são a fronteira do escopo *e* a lista de verificação do documento. Cada bullet precisa aparecer no **Percurso do escopo** com um desfecho explícito (ver abaixo). Nada fora dos bullets entra; nenhum bullet sai sem resposta.
2. **Pergunta direta** — descreve a dúvida no chat. A descrição É o escopo.
3. **Documento** — aponta um arquivo com o problema e as restrições.

Se vierem combinados, o item de plano define a fronteira dura (nada fora dele entra no documento) e o resto adiciona foco e contexto.

Se o escopo estiver vago demais para identificar decisões concretas ("investiga o banco" — qual aspecto? schema? concorrência? migração?), **pergunte antes de investigar**.

## Contexto a ler antes de investigar

1. **O plano do projeto** (`TODO.md`, `docs/`, ou equivalente) — o que já foi decidido é restrição, não assunto. Não reabra.
2. **Decisões anteriores** — se houver documentos de spike/decisão prévios, eles são vinculantes.
3. **As versões realmente instaladas** — leia o manifesto *e* o lockfile (`pyproject.toml`/`uv.lock`, `package.json`/`package-lock.json`, `go.mod`, `Cargo.toml`, …). Isso determina quais alternativas são compatíveis de verdade e qual versão da documentação importa.
4. **O código existente**, quando a investigação toca código que já está lá.

## O que é uma decisão de spike (e o que não é)

Uma decisão de spike é uma **escolha estratégica**: aquela cujos trade-offs quem implementa não consegue re-derivar sozinho na hora de codar.

Antes de escrever qualquer decisão, aplique o teste:

- **(a) A documentação ou a convenção do stack já resolve?** Se a resposta está num guia oficial, numa convenção canônica do framework ou numa skill de boas práticas, quem implementa converge sem precisar de decisão.
- **(b) É um contrato entre partes?** O item precisa ficar consistente em dois ou mais lugares que não se enxergam (schema + config + runtime; backend + frontend; tool + API)?

**Descarte** quando (a) vale e (b) não. **Mantenha** quando (a) falha ou (b) vale.

Exemplos de descarte: nome de arquivo seguindo convenção do framework; opção de módulo com default estabelecido; nome de script no package manager; estrutura de diretório idiomática.

Exemplos de manutenção: protocolo de upload; onde o token é armazenado; estratégia de concorrência na gravação; qual topologia de agentes preserva um comportamento.

Uma decisão que só existe porque apareceu numa checklist, sem nada no escopo que a exija, é extrapolação. Corte.

## Como investigar

1. **Fixe as versões primeiro.** Investigar a versão errada produz um documento confiante e falso.
2. **Leia o código-fonte instalado.** Em spike, ele é a autoridade final — mais confiável que a documentação, que descreve alguma versão, nem sempre a sua. Cite `arquivo:linha` para cada afirmação não-óbvia, para que o leitor confira sem refazer a investigação.
3. **Use Context7 e busca para a documentação da versão certa**, não da mais recente.
4. **Execute.** Um `grep` que confirma não é um teste que roda. Monte o harness descartável que for preciso: stub de dependência externa, processo separado, carga concorrente — o que a dúvida exigir. O que foi executado vale mais do que o que foi lido, e a diferença precisa aparecer no documento.
5. **Identifique o que de fato governa a resposta e teste isso.** Se a documentação, o código ou o enunciado indicam que um fator altera o resultado, ele é o objeto do teste — congelá-lo por conveniência produz uma resposta sobre um sistema que não será construído. Quando houver mais de um fator assim, varra a combinação e relate o que sobrevive.
6. **Quando documentação e código discordarem, registre a discordância.** Costuma ser um achado por si só.
7. **Seja honesto nos trade-offs.** Se duas opções empatam no contexto deste projeto, diga que empatam. Não force recomendação.

## Honestidade sobre cobertura

Um spike que esconde lacunas gera confiança falsa, que é pior que nenhuma informação. Separe sempre:

- **Verificado por execução** — rodou; este foi o resultado.
- **Verificado por leitura** — o código diz isto; não foi executado.
- **Não verificado** — e exatamente o que destrava (falta credencial? ambiente? dado?).

Se um bloqueio impediu parte da investigação, **entregue tudo que deu** e diga o que falta. Nunca finja cobertura.

Se você errou durante a investigação e corrigiu, **registre** quando o modo de falha for instrutivo — um resultado que parecia achado e era bug do harness ensina quem for repetir.

## Trabalho delegado

Se delegar partes da investigação, **verifique de forma independente antes de registrar como achado**. Relatório de subagente é entrada, não conclusão: rode você mesmo os comandos que sustentam cada afirmação.

## Percurso do escopo — item a item

Quando o escopo vem de uma lista (um `TODO.md`, uma fase, um conjunto de perguntas), o documento **percorre cada item**, na ordem, e fecha cada um com um desfecho explícito. Um de quatro:

| Desfecho | Quando usar | O que escrever |
|---|---|---|
| **Decisão** | há escolha real com trade-off | aponta para `D-NN`, definida na seção de decisões |
| **Resolvido** | a investigação respondeu | a resposta + a evidência (`arquivo:linha` ou saída de execução) |
| **Pontos levantados** | não é decisão, mas quem implementa precisa saber | o que importa: armadilha, restrição, ordem de execução, custo escondido |
| **Nada a acrescentar** | o item é direto e a convenção resolve | diga isso **em voz alta**, com uma linha de porquê |

A razão de o quarto existir: **silêncio por omissão é modo de falha, não resposta.** Um item que some do documento não se distingue de um item esquecido, e quem for implementar não tem como saber qual dos dois aconteceu. Se não há nada a dizer, dizer "não há nada a dizer, porque X" é informação — e custa uma linha.

Escolher entre **Decisão** e **Pontos levantados** é o mesmo teste do § anterior: se a convenção do stack resolve e não é contrato entre partes, não vire decisão — levante o ponto e siga.

### Checagem de cobertura — rode antes de emitir

Antes de escrever o documento, confira que **todo item do escopo tem desfecho**. Esta é uma porteira, não uma sugestão. Se faltar item, volte e investigue — não emita o documento incompleto esperando que ninguém note.

Se um item ficou sem desfecho por bloqueio real (falta credencial, ambiente, dado), ele **ainda aparece** no percurso, com desfecho *Pontos levantados* explicando o bloqueio e o que destrava — e entra também em *Não verificado*.

## Estrutura do documento

```markdown
# Spike: <a incerteza, formulada como pergunta>

**Status:** <concluído | parcial — o que faltou>
**Versões investigadas:** <libs e versões exatas>
**Harness:** <onde está o código descartável, e como foi rodado>

## Resumo executivo
<A parte mais lida do documento. Escrita para quem nunca viu o projeto —
ver § "Escreva para quem não estava na conversa". Quatro movimentos:>

### Do que se trata
<O sistema, em 2-3 frases, para alguém sem nenhum contexto.>

### Por que este documento existe
<A pergunta que estava aberta e o que ela bloqueava.>

### O que foi encontrado
<Os achados que mudam alguma coisa. Cada um num parágrafo que se sustenta
sozinho, com o vocabulário do projeto definido na primeira aparição.>

### O que se espera de você
<As decisões que ficam para o leitor, enunciadas de forma compreensível
sem ele precisar descer até a seção delas.>

## A pergunta
<A incerteza e por que ela bloqueia.>

## Como funciona
<Overview de comportamento: o mecanismo descoberto, em prosa. Esta seção
ensina o leitor, não só registra o achado. Acompanhe de diagrama quando
houver fluxo ou topologia (ver abaixo).>

## Cenários
<Gherkin, quando o comportamento tiver regras observáveis a amarrar.>

## Achados
<Numerados. Cada um com a evidência (arquivo:linha ou saída de execução)
e a consequência prática.>

## Restrições derivadas
<O que a investigação provou ser obrigatório ou proibido. É o que limita
o espaço de design daqui para frente — e o que torna algumas das decisões
abaixo mais fáceis.>

## Percurso do escopo

<Um bloco por item do escopo, na ordem original, com o texto do item
reproduzido literalmente. Nenhum item sai sem desfecho.>

### <item do escopo, literal>
**Desfecho:** Decisão D-NN | Resolvido | Pontos levantados | Nada a acrescentar

<Se Resolvido: a resposta e a evidência.
 Se Decisão: uma linha dizendo qual é a escolha, e o ponteiro para D-NN.
 Se Pontos levantados: o que quem implementa precisa saber.
 Se Nada a acrescentar: por que não há nada a decidir aqui.>

---
(repete para cada item)

**Cobertura:** <N> itens no escopo · <N> resolvidos · <N> viraram decisão ·
<N> com pontos levantados · <N> sem nada a acrescentar.

## Não verificado
<Separado por motivo, com o que destrava cada item.>

## Decisões em aberto

### D-01: <nome da decisão>

**Contexto:** por que esta decisão precisa ser tomada e o que depende dela.

**Opção A: <nome>**
- Como funciona (2-3 linhas)
- **A favor:** vantagens concretas
- **Contra:** desvantagens concretas

**Opção B: <nome>**
- Como funciona (2-3 linhas)
- **A favor:** ...
- **Contra:** ...

**Recomendação:** <opção> — uma frase de justificativa ancorada neste projeto.

**Decisão:** _[pendente]_

---
(repete para cada decisão)

## Resumo das decisões

| ID | Decisão | Recomendação | Escolha |
|----|---------|--------------|---------|
| D-01 | <nome> | <opção> | _[pendente]_ |

## Próximos passos
<Só o que decorre do spike.>
```

### Diagramas

Use Mermaid — renderiza no GitHub e no editor, e fica versionado junto do código. `sequenceDiagram` para fluxos com ida e volta (protocolos, retomada, retry); `flowchart` para topologia de componentes.

Mostre **chamadas reais com nome e assinatura**, não caixas genéricas: `consultar_disponibilidade(area, data) → {livre: bool}` ensina; "Tool Call" não. Marque com ⚠️ o que ainda é desconhecido.

Quando o diagrama corrigir um entendimento anterior — do usuário, de um rascunho, da documentação — **diga que corrigiu e por quê**. Divergência silenciosa vira confusão depois.

### Cenários

Escreva Gherkin só onde houver regra observável a amarrar. Eles servem para fixar o comportamento esperado antes da implementação e virar base dos testes depois. Cubra os caminhos negativos e de borda — "dado que a confirmação já foi respondida, quando reenviam o mesmo id, então 409 e nada executa" vale mais que o caminho feliz, que ninguém esquece.

Quatro disciplinas que separam cenário útil de cenário decorativo:

- **Uma ação sob teste por cenário.** Tudo que apenas prepara o terreno vai no `Dado`, mesmo sendo algo que o sistema executa. Encadear `Quando X` + `E Y` com duas ações independentes não testa a combinação: testa duas coisas mal, e sugere ao leitor um acoplamento entre elas que o sistema não tem — alguém lê "cancela, e então o outro reserva" e imagina uma fila de intenções que não existe.
- **Pergunte o que quebraria se o cenário não existisse.** Se a resposta for "nada, isso decorre de outro invariante", corte. Cenário bom aponta para um modo de falha plausível, não para uma verdade já garantida em outro lugar.
- **Verifique se o cenário é sequer satisfazível no modelo proposto.** Um cenário pode enunciar uma exigência real e ainda assim ser impossível de cumprir sob a modelagem em discussão — "o código de uma entidade excluída nunca é reutilizado" não tem como ser verdade se a exclusão apaga o registro. Quando isso acontecer, o achado não é o cenário: é que **a exigência elimina uma opção de modelagem**. Leve isso para as restrições derivadas, e remova a opção eliminada da seção de decisões em vez de deixá-la competindo.
- **Cenário que só tem valor sob uma decisão pendente precisa dizer isso.** Marque com um comentário citando a decisão (`# só tem valor se … — ver D-NN`), para ninguém implementar um teste que a decisão pode tornar vazio.

## Escreva para quem não estava na conversa

O documento sobrevive à conversa que o gerou. Quem o abrir — outra pessoa do time, o avaliador do trabalho, você mesmo daqui a duas semanas — **não tem o contexto que você tem agora**, e não vai reconstruí-lo. Texto escrito a partir de dentro da investigação vira nota pessoal: frases corretas, encadeamento invisível.

Vale explicitar o erro de origem, porque ele é sistemático: **quem lê não é um agente com a sua janela de contexto.** Você acabou de ler o enunciado, o plano, o código-fonte e meia dúzia de arquivos de dados, e tudo isso está vivo na sua cabeça enquanto escreve. O leitor tem só o arquivo aberto na frente dele. Toda ponte que você não construir explicitamente, não existe.

**Isso vale para o documento inteiro, não só para o resumo.** Cada seção precisa ser legível por quem caiu direto nela — alguém mandou o link apontando para a seção de decisões, ou o leitor voltou três semanas depois para conferir um achado. Uma seção que só faz sentido depois de ler as anteriores na ordem é uma seção que vai ser mal lida.

O sintoma é fácil de reconhecer e fácil de não notar enquanto se escreve:

- o texto começa a falar do achado sem nunca dizer **de que sistema se trata**;
- usa nomes próprios do projeto — "Garantia 2", "passo 10", "o Transacional", "a Fase 1.2" — como se fossem de conhecimento geral;
- referencia o plano ("o TODO tratava isso como um só") assumindo que o leitor o tem aberto ao lado;
- enuncia conclusões sem a pergunta que elas respondem.

O **Resumo executivo** é onde isso mais dói, porque é o que a maioria vai ler. Ele precisa, nesta ordem, responder quatro coisas:

1. **De que se trata** — o que é o sistema, em duas ou três frases, para alguém que nunca ouviu falar dele.
2. **Por que este documento existe** — qual pergunta estava aberta e o que ela bloqueava.
3. **O que foi encontrado** — os achados que mudam alguma coisa, cada um explicado por inteiro no próprio parágrafo.
4. **O que se espera do leitor** — quais decisões ele precisa tomar, enunciadas de forma compreensível sem descer até a seção delas.

Duas regras que resolvem a maior parte do problema:

- **Defina o vocabulário do projeto na primeira vez que usar.** "Garantia 2" não significa nada sozinho; "a exigência de que cada sessão pertença a um apartamento e nada que o morador escreva alcance outro (a *Garantia 2* do enunciado)" significa. Vale para números de passo, nomes de componentes internos e jargão de domínio — inclusive o que você mesmo cunhou neste documento.
- **Cada achado é um parágrafo que se sustenta sozinho.** Não encadeie achados por contraste ("o segundo achado…") sem que o primeiro tenha ficado completo. Quem lê salteado precisa entender o parágrafo em que caiu.

E nas demais seções, três hábitos que custam pouco:

- **Cada decisão `D-NN` repete o mínimo de contexto para ser decidida isolada.** O campo `Contexto:` existe para isso: quem abre o documento só para decidir precisa entender a pergunta sem subir até os achados.
- **Diagrama e cenário vêm com uma linha de legenda.** Um Mermaid sem frase de abertura obriga o leitor a inferir o que está olhando.
- **Ao citar evidência, diga o que ela é.** `_confirmation.py:295` não informa nada sozinho; "o processador de confirmação do ADK (`_confirmation.py:295`)" informa.

**Teste antes de emitir:** leia o documento imaginando que você nunca viu o projeto. Dois pontos de controle — se em qualquer um deles precisar perguntar "mas isso é sobre o quê?", reescreva:

1. os dois primeiros parágrafos do resumo executivo;
2. **qualquer seção aberta isoladamente**, começando pelas de decisões.

Isso não é pedido para inflar o texto. Contexto bem dado costuma custar três frases; a falta dele custa o documento inteiro.

## Como escrever opções e recomendações

A recomendação é sugestão, não decisão. Ela precisa:

- ser justificada pelo **contexto deste projeto**, não por preferência genérica;
- considerar o que já foi decidido antes;
- ser explícita sobre o que se ganha e o que se perde;
- admitir quando não há diferença relevante.

Ruim: *"SQLite é mais simples."*
Bom: *"SQLite porque a exclusividade exigida precisa valer no instante da gravação, e um índice único parcial resolve isso sem adicionar serviço externo — que o enunciado obrigaria a documentar com comando de subida."*

Ruim: *"Use `chat`, é o padrão."*
Bom: *"`chat` gasta menos chamadas ao modelo, o que importa porque o avaliador faz dezenas delas e um dos passos dispara aprovações concorrentes. O custo é que o especialista segue ativo e pode responder fora do domínio dele."*

## Regras

- **Todo documento abre estabelecendo de que sistema se trata** — sem exceção, por mais óbvio que pareça de dentro da conversa. Quem lê não tem a sua janela de contexto.
- **Nunca preencha o campo `Decisão:`.** Ele é do usuário. Recomende e pare.
- **Todo item do escopo aparece no Percurso, com desfecho.** Omitir um item é indistinguível de esquecê-lo. Quando não houver nada a dizer, diga que não há e por quê.
- Não force item de escopo a virar decisão só para engrossar a seção. A maioria dos itens de um TODO bem escrito resolve em *Resolvido* ou *Pontos levantados*.
- Entre **2 e 4 opções** por decisão. Menos de 2 não é decisão; mais de 4 é ruído.
- Não inclua opções claramente inadequadas ao stack só para encher a lista.
- Quando uma decisão depende de outra, **diga qual** e em que sentido.
- Quando uma restrição derivada já elimina opções, **mostre isso** em vez de listar alternativas mortas.
- Quando uma decisão depende de algo que ficou **não verificado**, marque a dependência explicitamente — e ofereça verificar antes que o usuário decida no escuro.
- Mantenha cada opção curta. Passou de 5-6 linhas, está virando implementação.
- Não entre em detalhe de implementação: aplique o teste (a)+(b) e corte o que a convenção do stack já resolve.

## Saída

Salve em **`docs/spike-<id>-<slug>.md`**, onde `<id>` é **o identificador do item no plano** (`TODO.md`) que originou o spike, e `<slug>` é um nome curto e descritivo do tema.

```
docs/spike-1.1-dominio-invariantes.md      ← item 1.1 do plano
docs/spike-1.2-fronteiras-agentes.md       ← item 1.2
docs/spike-R1-confirmacao-de-tools.md      ← investigação de risco R1
```

O número vem primeiro por um motivo prático: o diretório ordena na mesma sequência do plano, e quem abre `docs/` vê imediatamente o que já foi investigado e o que falta. Slug sozinho obriga a abrir arquivo para descobrir a que fase pertence.

**Se o item do plano não tiver identificador**, dê um a ele no `TODO.md` antes de nomear o arquivo — não invente um número só para o nome. Identificador que existe no arquivo e não existe no plano é pior que nenhum: ele parece rastreável e não é.

**Nunca repita um `<id>`.** Dois arquivos reivindicando o mesmo número tornam ambíguo qual decisão veio de onde, que é exatamente o que a numeração deveria resolver. Se um item gerar mais de um spike, sufixe (`1.2a`, `1.2b`) e registre os dois no plano.

Ao terminar, diga ao usuário em uma linha: onde está o documento, quantas decisões aguardam ele, e quais delas dependem de algo ainda não verificado.
