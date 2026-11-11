# ADR-0001 — Cancelar uma reserva marca `ativa = 0`; a linha permanece na tabela

**Status:** aceito
**Data:** 2026-11-08
**Origem:** [`docs/spike-1.1-dominio-invariantes.md`](../spike-1.1-dominio-invariantes.md) → `dominio/D-06`
**Invariantes e garantias afetados:** `I-01`, `I-03`; regras de negócio 1 e 5 do enunciado
**Relacionado:** ADR-0004 (o contrato de cancelamento que opera sobre esta coluna)

## Contexto

O Residencial Aurora é um assistente de condomínio: o morador conversa por chat e reserva áreas comuns, cancela as próprias reservas e autoriza visitantes. Toda reserva recebe um código gerado pelo sistema (`RSV-1377`, `RSV-4821`).

O enunciado do desafio impõe duas regras sobre reservas que, juntas, decidem a modelagem:

- **Regra 1** — cada área comum aceita no máximo **uma reserva por data**.
- **Regra 5** — o código de uma reserva nova **nunca repete o de outra reserva, inclusive o de uma reserva cancelada**.

A segunda elimina uma opção inteira antes de qualquer discussão de preferência. Para o sistema garantir que um código jamais se repete, ele precisa **continuar sabendo que aquele código existiu**. Se cancelar apagar o registro, esse conhecimento desaparece junto e nada tem como detectar a repetição depois — a regra se torna inexequível, não apenas difícil. Cancelamento como exclusão física está, portanto, fora de cogitação.

O que restava decidir não era *se* o histórico é retido, mas **onde** — e essa escolha determina se a unicidade é imposta pelo banco ou por disciplina do código nosso.

## Decisão

Cancelar uma reserva **marca `ativa = 0`**; a linha permanece na tabela `reserva`. A tabela carrega dois índices com **escopos diferentes**:

| Índice | Escopo | Garante |
|---|---|---|
| `UNIQUE (codigo)` | a tabela inteira, ativas e canceladas | regra 5 — o código nunca se repete |
| `UNIQUE (area, data) WHERE ativa = 1` | apenas as ativas | regra 1 — uma reserva por área/data, e a data volta a ficar livre após um cancelamento |

Toda leitura de reserva destinada ao morador filtra `ativa = 1`.

## Alternativas consideradas

- **Exclusão física.** Eliminada por restrição, não por preferência: torna a regra 5 inexequível (ver *Contexto*).
- **Mover canceladas para uma tabela de histórico.** A tabela ativa ficaria limpa e nenhuma leitura precisaria de filtro — mas a unicidade do código passaria a valer sobre duas tabelas, o que não se expressa em um índice. Viraria verificação em código, exatamente o tipo de garantia frágil que o enunciado penaliza (ele exige que a exclusividade valha "no instante da gravação").
- **UUID ou aleatório longo, sem reter histórico.** Não implementa a garantia: a abandona e aposta que a colisão não ocorre. O enunciado diz "nunca repete", não "quase nunca", e o avaliador confere os códigos criados contra os anteriores. Um gerador aleatório continua válido **dentro** desta decisão — o que não vale é usá-lo como substituto da retenção.

## Consequências

**O que fica mais fácil:** a unicidade perpétua do código passa a ser imposta pelo banco, com um índice e nenhuma linha de código. Cancelamento vira um `UPDATE`, operação barata e atômica. O histórico fica disponível para depuração sem estrutura extra.

**O que fica mais difícil, ou passa a custar atenção:** existem agora **duas regras de unicidade com escopos diferentes na mesma tabela**, e confundi-las quebra o sistema de formas opostas. Um `UNIQUE (area, data)` sem a cláusula parcial impediria para sempre que uma data cancelada fosse reservada de novo; um índice de código que não cobrisse as canceladas deixaria o código se repetir. Além disso, **toda** leitura precisa filtrar `ativa = 1` — esquecer em um único lugar vaza reserva cancelada para a conversa do morador.

**Risco aceito:** o filtro `ativa = 1` é disciplina de código, não garantia do banco. A mitigação é arquitetural — todas as leituras passam pelo repositório, que é uma interface única (`app/dominio/repositorio.py`) — mas nada impede que uma consulta nova esqueça o filtro. Há cenário dedicado a isso.

## Verificação

| Cenário | Protege | Tipo |
|---|---|---|
| Cancelar a própria reserva libera a data | `I-01` | positivo |
| Data liberada por cancelamento aceita nova reserva de outro apartamento | `I-01` sob soft delete | **regressão** — falha se o índice for `UNIQUE(area, data)` sem a cláusula parcial |
| Código nunca se repete, nem o de uma reserva cancelada | `I-03` | **regressão** — falha no dia em que alguém "simplificar" o cancelamento para `DELETE` |
| Reserva cancelada não aparece nas reservas do morador | o filtro `ativa = 1` | **regressão** — falha se uma leitura esquecer o filtro |

Arquivo: `tests/features/reservas.feature`

## Onde isso vive no código

| O quê | Onde |
|---|---|
| Coluna `ativa` e os dois índices | `app/infra/banco.py` → `DDL`, 3º e 4º comandos |
| `UNIQUE (codigo)` sobre a tabela inteira (I-03) | `app/infra/banco.py` → `codigo TEXT PRIMARY KEY` |
| `UNIQUE (area, data) WHERE ativa = 1` (I-01) | `app/infra/banco.py` → `ix_reserva_area_data_ativa` |
| Cancelar grava `ativa = 0`, não apaga | `app/infra/repositorio_postgres.py` → `_cancelar` |
| Filtro `ativa = 1` nas leituras | `app/infra/repositorio_postgres.py` → `listar_reservas_do_apartamento`, `data_esta_livre` |

| Schema aplicado ao subir a aplicação | `app/api/aplicacao.py` → `criar_app` (ADR-0006) |

Verificado por 4 cenários em `tests/features/reservas.feature`, todos verdes.
