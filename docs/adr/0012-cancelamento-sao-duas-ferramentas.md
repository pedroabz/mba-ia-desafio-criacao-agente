# ADR-0012 — O cancelamento são duas ferramentas, cada uma com parâmetros obrigatórios

**Status:** aceito
**Data:** 2026-11-08
**Origem:** [`docs/spike-1.3-superficie-de-tools.md`](../spike-1.3-superficie-de-tools.md) → `superficie/D-03`
**Invariantes e garantias afetados:** `I-02`, `I-06`; regra de negócio 4
**Relacionado:** ADR-0004 (decidiu aceitar as duas formas de identificar a reserva)

## Contexto

O ADR-0004 decidiu que o morador pode cancelar uma reserva identificando-a de duas maneiras: pelo par `(área, data)` ou pelo `código` — sempre com o dono validado. O que ele não disse é **como isso aparece para o modelo**: uma ferramenta que aceita os três campos como opcionais, ou duas ferramentas distintas.

A diferença pesa mais aqui do que pesaria em outra operação, por causa da regra de negócio 4: *"o morador pode cancelar as reservas do próprio apartamento, **sem confirmação**"*. O cancelamento é a única ação destrutiva do sistema que executa **sem o morador aprovar** — não há portão entre o pedido e o efeito, e a data liberada pode ser tomada por outro apartamento no instante seguinte.

## Decisão

**Duas ferramentas**, cada uma com todos os parâmetros obrigatórios:

| Ferramenta | Parâmetros |
|---|---|
| `cancelar_reserva_por_area_e_data` | `area`, `data` — ambos obrigatórios |
| `cancelar_reserva_por_codigo` | `codigo` — obrigatório |

Nenhuma delas aceita parâmetro opcional. As duas validam o dono contra o apartamento da sessão, e as duas produzem a mesma recusa quando a reserva não é do morador ou não existe (ADR-0004).

## Alternativas consideradas

- **Uma ferramenta com três parâmetros opcionais** (`area`, `data`, `codigo`), validando em código qual combinação é aceitável. Menos ferramentas na lista do modelo e um só lugar para a lógica de cancelamento. Rejeitada porque empurra para o nosso código uma validação que o schema pode fazer sozinho: *"veio `area` sem `data`"* é um estado que, na Opção A, só é pego por um `if` que alguém precisa ter escrito — e, na Opção B, **não é representável**. Dado que o cancelamento executa sem confirmação, quanto menos caminho ambíguo até ele, melhor.

## Consequências

**O que fica mais fácil:** o modelo não consegue chamar o cancelamento com uma combinação incompleta de argumentos — a declaração não permite. Cada ferramenta tem uma docstring curta sobre um jeito só de pedir.

**O que fica mais difícil, ou passa a custar atenção:** duas ferramentas a mais na lista do especialista de Reservas, que passa de quatro para cinco. E a validação de dono existe em dois lugares.

Essa duplicação é menos real do que parece: são duas cláusulas `WHERE` em dois métodos do repositório que **já existem e já estão cobertos por cenários `@storage` verdes** (`cancelar_reserva_por_area_data` e `cancelar_reserva_por_codigo`). A decisão não cria caminho novo; ela só deixa de escondê-los atrás de uma assinatura única.

**Risco aceito:** com cinco ferramentas no especialista de Reservas, duas delas quase homônimas, cresce a chance de o modelo escolher a errada — pedir cancelamento por código quando tem área e data em mãos, e falhar. O custo é um turno e uma nova tentativa, não uma ação errada: a ferramenta errada com argumentos que ela não tem simplesmente não é chamável. **Não medido com modelo real.**

## Verificação

| Cenário | Protege | Tipo |
|---|---|---|
| Cancelar citando área e data cancela a reserva certa | a decisão deste ADR | positivo |
| Cancelar citando o código cancela a reserva certa | a decisão deste ADR | positivo |
| Cancelar código de outro apartamento não altera nada e não confirma a existência | `I-02`, `I-06`, ADR-0004 | **regressão** |

Arquivo: `tests/features/ferramentas.feature`

## Onde isso vive no código

| O quê | Onde |
|---|---|
| `cancelar_reserva_por_area_e_data` | `app/agentes/ferramentas/reservas.py` |
| `cancelar_reserva_por_codigo` | `app/agentes/ferramentas/reservas.py` |
| Validação de dono | o `apartamento` na cláusula `WHERE`, em `repositorio_postgres.py` |
| Código alheio ≡ inexistente | `app/dominio/erros.py` → `ReservaNaoEncontrada` |

⚠️ `ReservaNaoEncontrada` **não aceita parâmetros**, e isso é deliberado: a
mensagem é genérica porque qualquer detalhe — o código pedido, o dono real —
reabriria a distinção que a exceção existe para apagar. Verificado por
sabotagem: acrescentar `codigo_procurado` à recusa derruba exatamente o
cenário de regressão.

Verificado por 3 cenários em `tests/features/ferramentas.feature`, todos verdes.
