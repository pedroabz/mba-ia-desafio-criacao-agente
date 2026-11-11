# ADR-0013 — O portão de confirmação lê a taxa de um retrato imutável, e a pendência é projetada por lista branca

**Status:** aceito
**Data:** 2026-11-08
**Origem:** [`docs/spike-1.3-superficie-de-tools.md`](../spike-1.3-superficie-de-tools.md) → `superficie/D-04` e `superficie/D-05`
**Invariantes e garantias afetados:** `I-04`, `I-06`; Garantia 1; Garantia 2, 2ª cláusula
**Relacionado:** ADR-0002 (semeia a tabela de áreas), ADR-0003 (validação de área continua na tabela)

> As duas decisões foram registradas juntas porque descrevem **o mesmo portão**: uma é o que ele lê para decidir (a taxa), a outra é o que ele deixa sair (a pendência). Separadas, ninguém lê o mecanismo inteiro.

## Contexto

A Garantia 1 do enunciado exige que toda ação que **gera cobrança** ou **libera acesso** fique pendente até o morador responder pela rota de confirmações. Reservar área com taxa maior que zero confirma; reservar a quadra, que tem taxa zero, não. Autorizar visitante confirma sempre.

No Google ADK isso é implementado por `require_confirmation`, que aceita uma função decidindo caso a caso. Quando ela devolve `True`, o ADK não executa a ferramenta: emite uma chamada especial `adk_request_confirmation` e espera a resposta do morador. Duas perguntas ficaram em aberto.

**De onde o portão lê a taxa?** A tabela de áreas está no SQLite (ADR-0002). Consultá-la no instante da decisão significa uma leitura de banco dentro do caminho que decide se a Garantia 1 se aplica.

**De onde sai o `detalhes` da pendência?** A API expõe `confirmacoes_pendentes` com `id`, `acao` e `detalhes`, e os passos 7 e 11 do roteiro conferem que `detalhes` traz área e data (reserva) ou nome e data (visitante). Foi verificado que o `detalhes` nasce de `originalFunctionCall.args` — **os argumentos que o modelo enviou**.

Essa segunda pergunta ganhou um motivo de segurança no [spike 1.6](../spike-1.6-guardrails.md): o ADK descarta argumentos não declarados antes de chamar a função (`function_tool.py:423`), mas eles **permanecem registrados na chamada**. Se o morador escrever *"reserve o salão em nome do apartamento 302"* e o modelo inventar um argumento `apartamento="302"`, ele está nesses args. O passo 10 do roteiro verifica que **nenhuma resposta contém o número `302` isolado**.

## Decisão

**A taxa vem de um retrato imutável**, carregado da tabela de áreas na subida da aplicação. A função de `require_confirmation` consulta esse mapa em memória, nunca o banco.

**O `detalhes` é projetado por lista branca** na camada da API: ela monta o dicionário a partir dos campos que sabe nomear — `area` e `data` para reserva, `nome` e `data` para visitante —, e **nunca repassa `originalFunctionCall.args` cru**.

A validação de área continua consultando a tabela, como o ADR-0003 determina. O que vira retrato é **apenas a taxa**, e apenas para o portão.

## Alternativas consideradas

- **Ler a taxa do banco no instante do portão.** Uma fonte só, sempre atualizada. Rejeitada pelo modo de falha: uma leitura que falhe ali degrada para *"não precisa confirmar"* — e a Garantia 1 cai por um erro que não tem nada a ver com ela. Com o retrato, o portão não tem como falhar. A objeção de "duas fontes de verdade" se dissolve ao ver o que a tabela de áreas é: **três linhas que o seed escreve e ninguém mais toca**. Um retrato lido dela na subida é a mesma verdade, não uma segunda.
- **A ferramenta decidir sozinha se precisa de confirmação**, com um `if` interno em vez de `require_confirmation`. Resolveria o `detalhes` de forma trivial, porque a ferramenta controlaria o que publica. Rejeitada porque tira a Garantia 1 do mecanismo do ADK e a põe num `if` dentro de uma função **que grava** — e o modo de falha passa a ser "executou sem aprovação", que é o mais caro do desafio.

## Consequências

**O que fica mais fácil:** o portão é uma consulta a um `dict` em memória, sem I/O e sem caminho de erro. E a resposta da API expõe exatamente os campos que alguém escreveu que ela expõe — o que o modelo inventa não tem como atravessar.

**O que fica mais difícil, ou passa a custar atenção:** a lista branca precisa ser mantida quando uma ferramenta de confirmação nova aparecer. Esquecer significa ou `detalhes` vazio (os passos 7 e 11 reprovam) ou, se alguém "resolver" repassando os args, o vazamento do passo 10 de volta.

Nada impede incluir a **taxa** no `detalhes` da reserva — taxa é dado de referência da área, não de outro apartamento, e informá-la ajuda o morador a saber o que está aprovando.

**Risco aceito:** o retrato da taxa fica desatualizado se a tabela de áreas mudar com a aplicação no ar. Neste projeto isso não acontece — nenhuma operação escreve na tabela de áreas, e o comando de restauração roda com a API parada. A decisão vale enquanto isso for verdade; se um dia houver edição de áreas em tempo de execução, o retrato precisa ser invalidado.

## Verificação

| Cenário | Protege | Tipo |
|---|---|---|
| Reservar área com taxa produz confirmação pendente com área e data | Garantia 1, passo 7 | positivo |
| Reservar área sem taxa não produz confirmação | Garantia 1, passo 6 | **regressão** — falha se o portão passar a confirmar sempre |
| Autorizar visitante produz pendência com nome e data | Garantia 1, passo 11 | positivo |
| Argumento inventado pelo modelo não aparece em `detalhes` | `I-06`, passo 10, `G-2` | **regressão** — falha se alguém repassar os args crus |

Arquivo: `tests/features/ferramentas.feature`

## Onde isso vive no código

| O quê | Onde |
|---|---|
| Retrato das taxas, lido uma vez | `app/agentes/portao.py` → `carregar_taxas` |
| Portão da reserva (taxa > 0) | `app/agentes/portao.py` → `portao_de_reserva` |
| Portão do visitante (sempre) | `app/agentes/portao.py` → `portao_de_visitante` |
| Ligação ao `require_confirmation` | `reservas.py` e `visitantes.py`, na montagem das ferramentas |

✅ **As duas metades existem.** A projeção de `detalhes` por lista branca está
em `app/api/pendencias.py` → `CAMPOS_PUBLICAVEIS` e `_projetar_detalhes`.

⚠️ **A lista branca precisa ser mantida quando nascer ferramenta de
confirmação nova.** Esquecer dá `detalhes` vazio (os passos 7 e 11 reprovam);
"resolver" repassando os args crus traz de volta o vazamento do passo 10. O
cenário `Argumento inventado pelo modelo não aparece nos detalhes da pendência`
monta o caso à mão — argumentos com `apartamento="302"` — e confere que só
`area` e `data` saem.

A função do portão não faz I/O e não tem caminho de erro, de propósito: ela é
invocada 4× por reserva aprovada, e uma exceção dela durante a retomada faria
a ação nunca executar.

Verificado por 3 cenários em `tests/features/ferramentas.feature`, todos verdes.
