# Decisões de arquitetura — Residencial Aurora

Registro permanente das decisões tomadas neste projeto. Cada arquivo guarda **uma decisão**, o contexto que a motivou, as alternativas que foram descartadas e por quê, e os cenários de teste que provam que ela continua valendo.

**Por que isto existe separado dos spikes.** Um documento de spike é artefato de momento: ele investiga, apresenta opções e fica datado assim que a dúvida é resolvida. A decisão precisa sobreviver a ele — com o motivo, e sem as opções rejeitadas atrapalhando a leitura. Quem abrir o código daqui a meses e perguntar *"por que soft delete e não exclusão?"* encontra a resposta aqui, não garimpando um spike antigo.

**ADR aceito não se reescreve.** Decisão revista vira ADR novo, e o antigo é marcado como substituído, com link para o sucessor. Apagar o antigo destruiria a informação mais útil do histórico: que aquele caminho já foi tentado.

## Índice

| # | Decisão | Status | Origem | Invariantes |
|---|---|---|---|---|
| [0001](0001-soft-delete-para-reservas-canceladas.md) | Cancelar marca `ativa = 0`; a linha permanece na tabela | aceito | `dominio/D-06` | `I-01`, `I-03` |
| [0002](0002-apartamentos-e-areas-semeados-no-sqlite.md) | Apartamentos e áreas semeados no SQLite a partir de `dados/` | aceito | `dominio/D-05` | — |
| [0003](0003-validar-area-em-runtime-contra-a-tabela.md) | A ferramenta valida a área em runtime, contra a tabela | aceito | `dominio/D-02` | — |
| [0004](0004-contrato-da-ferramenta-de-cancelamento.md) | Cancelamento aceita código ou área+data, uma por chamada, nunca sob ambiguidade | aceito | `dominio/D-03` + `D-04` | `I-02`, `I-06` |
| [0005](0005-recusar-autorizacao-de-entrada-duplicada.md) | Autorização de entrada duplicada é recusada, com aviso | aceito | `dominio/D-01` | — |
| [0006](0006-a-aplicacao-cria-o-schema-no-startup.md) | A aplicação aplica o schema ao subir; a restauração só recarrega dados | aceito | revisão do plano 1.1 | — |
| [0007](0007-tres-especialistas-por-fronteira-de-dominio.md) | Três especialistas: Reservas, Visitantes e Regulamento | aceito | `fronteiras/D-01` | — |
| [0008](0008-como-cada-especialista-e-acionado.md) | Reservas e Visitantes são `sub_agents` em `single_turn`; Regulamento é `AgentTool` | aceito | `fronteiras` + `R1` | `I-05` |
| [0009](0009-agente-principal-sem-ferramentas-de-dominio.md) | O principal roteia e não toca dados do condomínio | aceito | `fronteiras/D-02` | `I-02`, `I-06` |
| [0010](0010-datas-cruzam-a-fronteira-como-string.md) | Ferramentas recebem data como `str` e convertem internamente | aceito | `superficie/D-01` | — |
| [0011](0011-recusa-de-negocio-nunca-vira-erro-de-servidor.md) | Recusa de negócio nunca escapa como exceção | aceito | `superficie/D-02` | Garantia 5 |
| [0012](0012-cancelamento-sao-duas-ferramentas.md) | O cancelamento são duas ferramentas, sem parâmetro opcional | aceito | `superficie/D-03` | `I-02`, `I-06` |
| [0013](0013-o-portao-de-confirmacao.md) | Portão de confirmação: taxa por retrato, pendência por lista branca | aceito | `superficie/D-04`+`D-05` | `I-04`, `I-06` |
| [0014](0014-postgres-substitui-sqlite.md) | **Postgres com `pgvector` substitui o SQLite** | aceito | revisão do spike 1.4 | `I-01`, `I-03` |
| [0015](0015-recuperacao-semantica-do-regulamento.md) | O regulamento é recuperado por similaridade semântica | aceito | `regulamento/D-02`+`D-04` | `I-05` |
| [0016](0016-recuperacao-por-artigo-devolvendo-lista.md) | A recuperação é **por artigo** e devolve uma lista; a resposta cita | aceito | `regulamento/D-06`…`D-09` | `I-05` |
| [0017](0017-um-modelo-flash-lite-nos-quatro-agentes.md) | Os quatro agentes usam o mesmo modelo: `gemini-3.5-flash-lite` | aceito | `modelos/D-01` | — |
| [0018](0018-tres-tentativas-no-429-sem-fallback-de-modelo.md) | Três tentativas no `429`, com 2 s de espera; sem `FallbackModel` | aceito | `modelos/D-02` | Garantia 5 (passo 14) |
| [0019](0019-erro-de-quota-vira-503-com-retry-after.md) | Erro de quota vira `503` com `Retry-After`; a rota drena o gerador | aceito | `modelos/D-03` | contrato da rota de mensagens |
| [0020](0020-embeddings-do-gemini-embedding-001-em-768-dimensoes.md) | Embeddings do `gemini-embedding-001`, com `task_type`, em 768 dimensões | aceito | `modelos/D-04` | `I-05` |
| [0021](0021-busca-no-regulamento-devolve-ate-tres-artigos-com-corte-065.md) | A busca devolve até 3 artigos, com corte absoluto de 0,65 | aceito | `regulamento/D-08` | `I-05`, Garantia 4 |

Os cinco primeiros vêm de [`docs/spike-1.1-dominio-invariantes.md`](../spike-1.1-dominio-invariantes.md) (Fase 1.1 do plano).

O **ADR-0006 não veio de spike** — ele apareceu na revisão de um plano de implementação, quando ficou claro que nenhuma decisão anterior dizia quem cria o schema do banco. Vale o registro de que nem toda decisão nasce em investigação: algumas só se revelam quando o trabalho é descrito em passos, e é por isso que o plano é revisado antes de virar código.

## Cobertura dos invariantes

Os seis invariantes do domínio e o que os sustenta hoje:

| Invariante | Imposto por | ADR |
|---|---|---|
| `I-01` — uma reserva ativa por `(area, data)` | banco, índice único parcial | [0001](0001-soft-delete-para-reservas-canceladas.md) |
| `I-02` — operação age só sobre o apartamento da sessão | ferramenta, lendo o state | [0004](0004-contrato-da-ferramenta-de-cancelamento.md) |
| `I-03` — código nunca repete, nem de cancelada | banco, `UNIQUE(codigo)` sobre a tabela inteira | [0001](0001-soft-delete-para-reservas-canceladas.md) |
| `I-04` — cobrança/acesso só após confirmação | `require_confirmation` + rota de confirmações | _aguarda decisões de [`spike-R1-confirmacao-de-tools.md`](../spike-R1-confirmacao-de-tools.md)_ |
| `I-05` — regulamento nunca entra inteiro no contexto | recorte da ferramenta | _decidido (ADR-0015, 0016, 0020, 0021) e os vetores existem; falta a **ferramenta**, que precisa de plano. Os 7 cenários `@recuperacao` seguem `@pendente`._ |
| `I-06` — nenhum dado que identifique outro apartamento chega à conversa | projeção do retorno da ferramenta | [0004](0004-contrato-da-ferramenta-de-cancelamento.md) |

## O que ainda não virou ADR

As cinco decisões de [`spike-R1-confirmacao-de-tools.md`](../spike-R1-confirmacao-de-tools.md) continuam **pendentes** e por isso não têm registro aqui: modo do especialista transacional, topologia do especialista de regulamento, número de especialistas, `is_resumable` e organização das tabelas no SQLite.

Decisão pendente não vira ADR — silêncio não é escolha.
