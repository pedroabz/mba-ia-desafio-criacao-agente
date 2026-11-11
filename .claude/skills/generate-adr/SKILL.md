---
name: generate-adr
description: "Transformar decisões já tomadas em ADRs (Architecture Decision Records) permanentes e derivar, junto com cada ADR, os cenários de teste que protegem a decisão. Use SEMPRE que o usuário tiver preenchido o campo `**Decisão:**` de um documento de spike, ou decidido algo arquitetural na conversa, e esse registro ainda não existir em `docs/adr/`. Frases de gatilho: 'gere os ADRs', 'registre as decisões', 'transforme as decisões do spike em ADR', 'documenta a decisão', 'cria os cenários de teste das decisões', 'escolhi a opção A, e agora?', 'já decidi, pode seguir', 'registra o porquê dessa escolha', 'preciso justificar isso no README', 'vamos fechar o spike'. Também em inglês: 'generate the ADRs', 'record the decisions', 'write an architecture decision record', 'document this decision', 'turn the spike decisions into ADRs', 'derive the test scenarios for these decisions', 'I've decided, now what'. Use ainda quando uma decisão antiga for revista ou revertida — a revisão também é um ADR. Na dúvida entre registrar e seguir direto para o código, registre: decisão perdida não se recupera depois."
---

# ADR

Pegar uma decisão **já tomada** e produzir duas coisas: o **ADR**, que preserva a decisão e o motivo dela, e os **cenários** que verificam que ela continua valendo no código.

O fluxo deste projeto é **spike investiga → usuário decide → implementação**. Esta skill é a ponte entre a decisão e o código.

A regra que organiza tudo: você **registra**; o usuário já **decidiu**. Um ADR que melhora, reinterpreta ou completa a escolha do usuário não é registro — é uma decisão nova disfarçada.

## Por que esta skill existe

**O documento de spike é artefato de momento.** Ele existe para destravar uma dúvida e fica datado assim que a dúvida é resolvida. A decisão, porém, precisa sobreviver: com o contexto que a motivou, as alternativas consideradas e o motivo da escolha. Seis meses depois alguém olha o código e pergunta "por que soft delete e não exclusão?", e a resposta não pode estar perdida numa seção de um spike antigo cercada de opções que foram descartadas. O ADR isola **a decisão tomada** do **processo de decidir**.

**Neste projeto há uma razão imediata.** O entregável avaliado (ver § Entregável do enunciado) exige um README com uma seção **Arquitetura** que descreve cada agente, sua responsabilidade, como é acionado **e por quê**, e uma seção **Garantias** que aponta, para cada uma das cinco, o arquivo e o trecho que a implementa. Os ADRs são a matéria-prima direta dessas duas seções. Sem eles, essa prosa é reconstruída de memória no fim do projeto — exatamente quando o detalhe já se perdeu.

**Decisão sem verificação é intenção, não garantia.** Por isso os cenários saem **junto** com o ADR, enquanto o raciocínio está fresco: assim eles checam a *razão* da decisão. Derivados depois, na hora de implementar, tendem a testar o que foi construído em vez do que foi decidido — o que é circular e não pega regressão.

## Entrada

Um ou mais documentos de spike com decisões preenchidas. Para encontrá-las:

1. Leia a tabela **Resumo das decisões** do spike — ela dá o panorama em uma olhada.
2. Confirme em cada bloco `### <id> — <nome>` o campo `**Decisão:**`. A tabela pode estar desatualizada; o bloco é a fonte.
3. **Decisão ainda `_[pendente]_` não vira ADR.** Liste quais ficaram de fora e por quê, no relatório final. Não presuma que a recomendação do spike foi aceita — ela é sugestão, e o silêncio não é escolha.

Se nenhuma decisão estiver preenchida, pare e diga isso. Se o usuário decidiu **no chat** e não no documento, o ADR vale igual: registre a origem como a conversa (com a data) e ofereça anotar o spike.

Antes de escrever, verifique **coerência**. Se a escolha contraria uma restrição derivada (`C-N`), um invariante (`I-NN`) ou um ADR aceito anterior, **pergunte antes de registrar** — um ADR que o código não pode cumprir é pior que nenhum.

## O que vira ADR e o que não vira

Aplique o mesmo teste que a `generate-spike` usa para separar decisão estratégica de detalhe de implementação:

- **(a) A documentação ou a convenção do stack já resolve?** Se sim, quem implementa converge sem registro.
- **(b) É um contrato entre partes** que precisa ficar consistente em lugares que não se enxergam (schema + tool + rota; banco + runtime)?

**Descarte** quando (a) vale e (b) não. **Mantenha** quando (a) falha ou (b) vale.

Na prática, decisão que já passou por um spike quase sempre vira ADR — ela só chegou ao documento porque passou nesse mesmo filtro. Os casos que ficam de fora são outros:

- **Agrupe** decisões que só fazem sentido juntas num único ADR: se duas escolhas são a mesma tabela, o mesmo índice ou o mesmo contrato, separá-las produz dois registros que ninguém consegue ler isolados. Nunca agrupe decisões independentes só para reduzir a contagem.
- **Decisão revertida antes de virar código** não vira ADR. Ela fica no spike, que é o registro do processo.
- **Consequência mecânica de outra decisão** não vira ADR próprio: entra como consequência no ADR que a causou.

## Numeração e nome de arquivo

`docs/adr/NNNN-titulo-em-kebab-case.md`, com `NNNN` de quatro dígitos, **sequencial global** — não por spike, não por fase. Antes de criar, liste `docs/adr/` e use o maior número existente + 1. Número nunca é reaproveitado, nem de ADR substituído.

O título é **a decisão, em voz ativa**, não a pergunta que a originou: `0003-soft-delete-para-reservas-canceladas`, não `0003-como-garantir-codigo-unico`. Quem varre o diretório precisa ler as escolhas do projeto, não o histórico de dúvidas.

Mantenha `docs/adr/README.md` como índice: número, título, status, data e link. É a primeira coisa que alguém abre, e é o insumo mais barato para a seção Arquitetura do README final.

## Formato do ADR

Base: o template clássico de Michael Nygard (título, status, contexto, decisão, consequências), com três campos acrescentados para o que este projeto cobra — rastreabilidade, alternativas rejeitadas e o ponteiro para o código.

```markdown
# ADR-NNNN — <a decisão, em voz ativa>

**Status:** proposto | aceito | substituído por ADR-NNNN
**Data:** AAAA-MM-DD
**Origem:** [`docs/spike-<slug>.md`](../spike-<slug>.md) → `<id da decisão no spike>`
**Invariantes e garantias afetados:** `I-NN`, Garantia N do enunciado (ou "nenhum")
**Relacionado:** ADR-NNNN (depende de) · ADR-NNNN (substitui)

## Contexto

<O problema, para quem nunca viu o projeto. O que estava em jogo, qual
restrição apertava, o que dependia disso. Dois a quatro parágrafos.
Não é resumo do spike: é o mínimo para a decisão abaixo fazer sentido
isolada, sem abrir nenhum outro arquivo.>

## Decisão

<A escolha, em voz ativa e no presente: "Cancelar uma reserva marca
`ativa = 0`; a linha permanece na tabela e `codigo` é UNIQUE sobre ela
inteira." Uma frase que alguém possa conferir contra o código.>

## Alternativas consideradas

<Uma linha por alternativa rejeitada, com o motivo da rejeição. É o
campo que impede a decisão de ser reaberta por engano — sem ele, a
próxima pessoa reconsidera as mesmas opções sem saber que já foram
pesadas. Inclua as que o spike eliminou por restrição, dizendo qual.>

## Consequências

**O que fica mais fácil:** <...>

**O que fica mais difícil, ou passa a custar atenção:** <...>

**Risco aceito:** <o modo de falha que a decisão não elimina, e por que
foi aceito.>

## Verificação

<Os cenários que provam a decisão. Tabela com nome do cenário, o que
ele protege, e o arquivo onde ele vive. Ver § Derivação dos cenários.>

| Cenário | Protege | Tipo |
|---|---|---|
| <nome> | `I-NN` / a decisão deste ADR | positivo / regressão |

Arquivo: `tests/features/<tema>.feature`

## Onde isso vive no código

<Preenchido durante a implementação: `arquivo:linha` + o trecho que
impõe a decisão. É a única seção que se edita depois de aceita, e é o
que alimenta a seção Garantias do README final.>
```

**Consequências ruins são obrigatórias — no mínimo uma.** Um ADR que só lista benefícios é propaganda, não registro. Se a decisão parece não ter custo, o custo está escondido: releia o campo **Contra** da opção escolhida no spike, que já o tinha identificado. E quando a escolha do usuário contraria a recomendação do spike, registre a escolha sem recado nem lamento — o trade-off que ele aceitou vai em *Risco aceito*, que é onde ele é útil.

Alvo de tamanho: **uma página**. Passou disso, está virando documento de design.

## Status e ciclo de vida

- **proposto** — escrito, aguardando confirmação. Use quando você derivou o ADR de uma decisão do chat e quer que o usuário confira antes.
- **aceito** — vale, e o código deve cumpri-lo. É o estado normal de um ADR nascido de `**Decisão:**` preenchida.
- **substituído por ADR-NNNN** — foi revisto.

**ADR aceito não se edita no corpo.** Quando uma decisão é revista, escreva um ADR **novo** e marque o antigo como substituído, com link para o sucessor; o novo cita o antecessor em *Relacionado* e explica em *Contexto* **o que mudou** — o que se aprendeu que inverteu a escolha. Apagar ou reescrever o antigo destrói exatamente a informação que torna o histórico útil: quem repetir o raciocínio antigo não vai saber que ele já foi tentado.

Duas edições são legítimas depois de aceito: a seção **Onde isso vive no código** (ponteiros mudam com o código) e correção de erro de escrita.

## Rastreabilidade nas duas direções

Um ponteiro só num sentido se perde: quem chega pelo spike não encontra o ADR, e quem chega pelo ADR não encontra o processo.

- **ADR → spike:** o campo `**Origem:**`, com link e o id da decisão.
- **Spike → ADR:** anote o campo `**Decisão:**` do bloco correspondente com a escolha e o ponteiro — `**Decisão:** B — idempotente por (apartamento, nome, data) (ver [ADR-0003](adr/0003-....md))` — e atualize a coluna *Escolha* da tabela **Resumo das decisões**. Mais nada: **não reescreva o spike nem remova as opções rejeitadas.** O valor dele agora é ser o registro de como se decidiu.
- **ADR → invariante e garantia:** o campo `**Invariantes e garantias afetados:**`. É o que liga a decisão à seção Garantias do README final e ao mapa `garantia → arquivo → trecho`.
- **Cenário → ADR/invariante:** comentário na primeira linha de cada cenário (ver abaixo).

## Derivação dos cenários

Gherkin em português (`Funcionalidade` / `Cenário` / `Dado` / `Quando` / `Então`), seguindo as disciplinas que a `generate-spike` estabelece na sua seção `### Cenários` — **leia-as e reutilize-as**, não invente regras concorrentes. Em resumo: uma ação sob teste por cenário (preparação vai toda no `Dado`); pergunte o que quebraria se o cenário não existisse e corte o que já decorre de outro invariante; e confira se o cenário é **satisfazível** no modelo decidido — um cenário impossível sob a decisão não é um teste a escrever, é um sinal de que a decisão tem um problema, e isso volta para o usuário.

Para cada ADR, derive **dois tipos**, e os dois são obrigatórios:

**1. Positivo — o que a decisão habilita.** O comportamento que passa a ser possível ou garantido por causa dela.

**2. Regressão de arquitetura — o cenário que falha se alguém escolher a alternativa rejeitada.** É o que transforma o teste em proteção. Para derivá-lo, pegue a alternativa rejeitada em *Alternativas consideradas* e pergunte: **qual observação distinguiria as duas implementações?** Essa observação é o `Então`. Exemplo da forma: a decisão foi soft delete; a alternativa rejeitada apaga a linha; a observação que as separa é que o código de uma reserva cancelada nunca reaparece — e esse `Então` falha no dia em que alguém "simplificar" para `DELETE`.

Se nenhuma observação distingue a decisão da alternativa, registre isso: ou a escolha era reversível e não precisava de ADR, ou a diferença está num eixo que nenhum teste alcança (custo, legibilidade, risco de quota). Nos dois casos, diga em vez de inventar um cenário decorativo.

Marque cada cenário com a origem na linha anterior ao `Cenário:`:

```gherkin
# Protege ADR-0003 (soft delete) e I-03. Falha se o cancelamento voltar
# a ser exclusão física.
Cenário: Código de reserva cancelada nunca reaparece
```

Não derive cenário para consequência já coberta por outro ADR — aponte para o cenário existente na tabela *Verificação*. Cenário duplicado envelhece em lugares diferentes.

## Onde os cenários ficam

Em `tests/features/<tema>.feature` — **no diretório de testes, não em `docs/`**. A razão é a finalidade: cenário que o runner não coleta é cenário que ninguém roda, e cenário que ninguém roda se perde igual a documento. É a mesma regra que a skill `generate-bdd` aplica; as duas precisam concordar, senão metade dos cenários do projeto fica invisível para o `pytest`.

Agrupe **por tema do domínio** (`reservas.feature`, `visitantes.feature`, `sessao.feature`), não um arquivo por ADR. Um ADR costuma gerar dois ou três cenários, e um arquivo por ADR produz dezenas de arquivos minúsculos onde o mesmo vocabulário de `Dado` se repete. A rastreabilidade não depende do nome do arquivo: ela vem do comentário acima de cada cenário e do script de cobertura, que detecta ADR sem cenário e cenário apontando para ADR inexistente — verificação mais confiável que convenção de nome.

Quando um ADR é substituído, os cenários dele **não são apagados**: ou continuam válidos sob o sucessor (atualize o comentário), ou o ADR sucessor explica por que deixaram de valer e aí saem com justificativa registrada.

Esses cenários não substituem o script de validação contra o fluxo do avaliador (Fase 5 do `TODO.md`) — eles o **complementam por outro eixo**. O script prova que os 15 passos passam; os cenários provam que as decisões continuam valendo. Um passo do avaliador pode continuar verde com a arquitetura trocada por baixo; é essa lacuna que os cenários de regressão fecham.

Quando um cenário não é executável no ambiente atual (falta credencial, exige concorrência real, depende de reinício de processo), marque com um comentário dizendo o que destrava. Cenário que ninguém roda e ninguém sabe que não roda é pior que cenário ausente.

## Regras

- **Nunca decida nada.** ADR nasce de decisão tomada. Se faltar escolha, a skill certa é a `generate-spike`.
- **Nunca preencha o campo `Decisão:` de um spike** com a sua recomendação. Você só o anota com o que o usuário escolheu, acrescentando o ponteiro para o ADR.
- Decisão pendente fica de fora, e **aparece no relatório** — omitir é indistinguível de esquecer.
- Um ADR por decisão, ou por grupo coeso. Nenhum ADR guarda-chuva de "decisões da Fase 1".
- **Toda consequência ruim é obrigatória.** Mínimo uma, concreta.
- **Todo ADR tem cenário positivo.**
- **Cenário de regressão é obrigatório quando o ADR declara ou sustenta um invariante (`I-NN`)**, e opcional fora disso. A razão é prática: invariante é, por definição, uma afirmação que vale sempre e é observável — dele o cenário de regressão sempre se deriva. Já decisões sobre *superfície de risco* ou *acoplamento* (granularidade de uma ferramenta, onde um dado de referência é carregado) frequentemente não produzem nenhuma diferença observável pela API: as duas alternativas se comportam igual e divergem só no que acontece quando algo dá errado. Forçar cenário aí produz teste decorativo, e regra muito dispensada perde autoridade. Quando o ADR não declara invariante e você não encontra observação que separe as alternativas, **diga isso em uma linha** no lugar do cenário — é informação útil: significa que a decisão é reversível sem quebrar nada observável.
- ADR aceito não se reescreve: decisão nova, ADR novo, antigo marcado como substituído.
- Escreva para quem não estava na conversa — vale integralmente a seção homônima da `generate-spike`. Cada ADR é aberto isolado, por link, sem o resto do projeto ao lado.

## Saída

- `docs/adr/NNNN-titulo-em-kebab-case.md` por decisão registrada.
- `docs/cenarios/NNNN-<slug>.feature` correspondente.
- `docs/adr/README.md` atualizado.
- O spike de origem anotado nos campos `**Decisão:**` e na tabela de resumo.

Ao terminar, diga em poucas linhas: quais ADRs foram criados, quais decisões ficaram de fora e por quê, quantos cenários saíram e quais deles são de regressão — e se algum cenário não é executável hoje, o que destrava.
