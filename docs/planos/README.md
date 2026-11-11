# Planos de implementação — controle

Registro de todo plano do projeto e do estado dele. **Esta é a fonte de verdade sobre o que já foi construído**; o `TODO.md` diz o que falta investigar e decidir, os planos dizem o que falta construir.

Um plano nasce `rascunho`, vira `validado` quando o usuário aprova, e `executado` quando todos os passos terminaram **e os cenários que ele prometia ficaram verdes**. Nenhum plano é executado sem passar por `validado` — é o gate que impede decisão tomada em silêncio dentro de uma implementação.

## Estado

| Plano | Status | Implementa | Cenários que fez virar |
|---|---|---|---|
| [1.1 — persistência](../plano-1.1-persistencia.md) | ✅ **executado** em 2026-11-08 | ADR-0001, 0002, 0006 | 6 |
| [1.3 — ferramentas de domínio](../plano-1.3-ferramentas-de-dominio.md) | ✅ **executado** em 2026-11-08 | ADR-0010, 0011, 0012, 0013 | 17 |
| [1.4 — Postgres e recuperação semântica](../plano-1.4-postgres-e-recuperacao-semantica.md) | ✅ **executado** em 2026-11-08 | ADR-0014, 0015, 0020, e em parte 0016 | 7 (4 previstos + 3 que nasceram na execução) |
| [4 — finalizar o assistente](../plano-4-finalizar-o-assistente.md) | ✅ **executado** em 2026-11-09 | ADR-0007, 0008, 0009, 0011, 0013, 0015, 0016, 0017, 0018, 0019, 0021 | **51** — todos os `@pendente` |

## O que cada um entregou

### 1.1 — persistência · executado

Transformou em sistema o código de banco que existia mas nunca rodava fora de teste.

- `criar_app()` passou a criar o banco, aplicar o schema e falar com ele — antes construía um repositório em memória, e tudo que a API gravava morria com o processo
- `aurora-restaurar` e `aurora-servir`, os dois comandos que o enunciado exige
- A Garantia 3 passou a valer **para os dados**; para a sessão de conversa, ainda não (depende da Fase 4)

Verificado como o avaliador faria: clone sem banco → restaurar → subir → `GET /apartamentos/101/reservas` devolve `RSV-1377`.

> **Nota de processo.** A Fase 2.3 — schema, seed e repositório — foi implementada **antes** deste plano existir, direto da decisão para o código. É exatamente o que o gate de validação passou a impedir. Fica registrado porque o plano 1.1 cobre só o que veio depois.

### 1.4 — Postgres e recuperação semântica · executado

O SQLite saiu do projeto. Domínio, sessão do ADK e os vetores do regulamento vivem num Postgres com `pgvector`, que sobe por `docker compose`.

**O primeiro passo era o que podia matar o plano, e foi medido primeiro:** a retomada da confirmação com a sessão em Postgres, em **dois processos separados**. A pendência nasce no processo A sem gravar nada; o processo B, novo, aprova e a reserva é criada **exatamente uma vez**. O risco aceito do ADR-0014 não se materializou.

O que ficou de pé:

- `compose.yaml` com `pgvector/pgvector:pg17`, volume nomeado e healthcheck, na porta 5433 para não colidir com um Postgres local
- **isolamento por schema do Postgres em cada teste** — era o risco nomeado do P2; três rodadas seguidas, 20 verdes nas três, zero schema deixado para trás
- `aurora-restaurar` indexa **96 artigos** do regulamento em **uma** requisição ao Gemini, em menos de 5 segundos
- o fatiamento é por **artigo**, com o capítulo embutido no vetor (ADR-0016): 96 artigos, 14 capítulos, nenhum truncado

**Dois bugs reais encontrados na execução, e nenhum dos dois estava previsto no plano:**

1. **Conexão do `asyncpg` presa ao event loop que a abriu.** Os passos do `pytest-bdd` são síncronos e cada um roda num loop novo; com pool, o segundo passo de um cenário morria com `got Future attached to a different loop`. Derrubou 29 cenários de uma vez. Corrigido com `NullPool`.
2. **O `.env` nunca era carregado no `os.environ`** — e o `google-genai` lê a chave de lá. Com uma chave válida no arquivo, `aurora-restaurar` recusava dizendo que não havia chave, **no passo 1 do roteiro do avaliador**, que é exatamente *preencher o `.env` e restaurar*. Invisível porque a mensagem era plausível. Virou cenário de regressão.

Também ficou claro que a mensagem certa não basta estar certa: o comando deixava a exceção propagar, e o avaliador veria vinte linhas de rastro de pilha antes dela. Virou um cenário próprio — o `criar_app` e o **comando** são pontos de entrada diferentes e falhavam diferente.

**A medição que o `regulamento/D-08` esperava agora existe.** Com os 96 vetores reais, a busca separa: acertos dentro do escopo em 0,699–0,763, falsos positivos fora do escopo em 0,556–0,598 — folga de ~0,10. Inclusive o caso que derrubou a busca léxica no spike 1.4: *"pode levar cachorro na quadra?"* recupera o Art. 56, do Capítulo VIII. Com esses números na mão, o corte foi decidido em seguida — **até 3 artigos, corte 0,65** ([ADR-0021](../adr/0021-busca-no-regulamento-devolve-ate-tres-artigos-com-corte-065.md)) — e a ferramenta de busca saiu de bloqueada para o passo P1 do [plano 4](../plano-4-finalizar-o-assistente.md).

**Revisado em 2026-11-08**, na consolidação do spike 2.4, antes de executar: a seção *"decisão pendente"* saiu (ADR-0020 escolheu o modelo e a dimensão); o `P4` deixou de citar `regulamento/D-01` como pendente (substituída pela `D-07`, decidida no ADR-0016); e os três critérios de pronto que apontavam para cenários inexistentes passaram a apontar para cenários que existem.

### 1.3 — ferramentas de domínio · executado

As sete ferramentas do assistente passaram a existir — antes `app/agentes/` estava vazio.

- `app/agentes/portao.py` — o portão de confirmação, com a taxa lida uma vez na subida
- `app/agentes/ferramentas/` — cinco de reserva, duas de visitante
- **Bug corrigido:** `data_esta_livre` não validava a área, e perguntar pela piscina devolvia "livre". O ADR-0003 decidiu validar em runtime; tinha sido implementado em `criar_reserva` e esquecido ali.

As três regressões foram provadas por sabotagem: confirmar sempre, revelar o dono na disponibilidade, e distinguir código alheio de inexistente — cada uma derruba exatamente um cenário.

**Dois ADRs ficaram pela metade, de propósito e registrado neles:** o `on_tool_error_callback` do ADR-0011 precisa de agente (Fase 4), e a projeção de `detalhes` do ADR-0013 precisa da rota de confirmações (3.2).

### 4 — finalizar o assistente · executado

Os quatro agentes, as duas rotas de conversa, a busca no regulamento e o
tratamento de quota. **Os 51 cenários `@pendente` ficaram verdes**, e a
etiqueta deixou de existir no projeto.

**Três ADRs nasceram da execução, não do ciclo de spikes** — os três vieram de
um cenário ficando vermelho, que é para isso que eles servem:

- **[ADR-0022](../adr/0022-a-busca-segue-remissoes-explicitas-de-capitulo.md)** — a busca não achava o Art. 16, que tem o horário do silêncio, e a causa era o ADR-0016: com o capítulo embutido no vetor, os 8 artigos do "Capítulo VI: Salão de festas…" casam com qualquer pergunta que diga "salão". Corrigido seguindo a remissão que o próprio texto faz.

**Quatro bugs reais, e três deles eram a mesma coisa por portas diferentes:**

1. **A chave não chegava ao ADK.** Com o modelo como string, ele lê `GOOGLE_API_KEY` do `os.environ`, onde o `.env` não chega — o mesmo bug do ADR-0020, pela segunda vez.
2. **Pool de conexão contra event loop**, de novo: o engine interno do `DatabaseSessionService` não é nosso e não usava `NullPool`. Apareceu nos passos do pytest-bdd, no `TestClient` (que monta um portal por requisição) e no harness de dois processos.
3. **Faltava `timeout`.** A suíte "não terminava": 4min26 com 13 s de CPU e 12 conexões penduradas. `HttpRetryOptions` reage a **erro**, e socket pendurado é **silêncio** — o timeout é o que transforma um no outro.
4. **Dois testes meus checavam prosa, não efeito.** Um exigia `?` na resposta; o modelo escreveu "Por favor, informe qual delas…", que é certo e não tem interrogação.

Também apareceram **duas colisões de passo** do tipo que o projeto já havia pago: `cancelar a reserva {codigo}` casando com `do 302`. O remédio registrado — texto do cenário mais específico, não passo mais esperto — foi aplicado nas duas.

## Planos ainda não escritos

**Nenhum, e desta vez porque não falta nada a construir.** O plano 4 fechou as
três linhas que ocupavam esta tabela — agentes, ferramenta de busca no
regulamento e rotas de conversa.

E **não há mais decisão pendente em spike nenhum** (conferido spike por spike
em 2026-11-08). As últimas três:

| Decisão | Como fechou |
|---|---|
| `regulamento/D-08` | a medição do plano 1.4 destravou → [ADR-0021](../adr/0021-busca-no-regulamento-devolve-ate-tres-artigos-com-corte-065.md), até 3 artigos com corte 0,65 |
| `R1/D-04` | resumability **desligado** — ligar exigiria tools idempotentes que ninguém escreveu assim |
| `rotas/D-03` | **A no código, B num teste** — a varredura é nossa porque o README precisa apontar código nosso; a função do ADK entra como juiz num cenário |

Mais duas foram marcadas como **obsoletas em vez de respondidas**, porque a
pergunta deixou de existir: `R1/D-05` (como organizar o SQLite, que saiu do
projeto) e `regulamento/D-01`/`D-03`, substituídas pela `D-07`/`D-08` quando a
busca virou semântica.

## Como ler isto junto do resto

```
TODO.md          o que falta investigar e decidir
docs/spike-*     como se chegou a cada decisão
docs/adr/        o que foi decidido, e por quê
docs/planos/     ← você está aqui: o que falta construir, e o que já foi
tests/features/  o que prova que tudo isso continua valendo
```

Para saber se um plano executado continua valendo, rode a suíte: os cenários que ele fez virar são a prova viva. Um plano marcado `executado` cujos cenários estão vermelhos é um plano que regrediu, não um plano concluído.
