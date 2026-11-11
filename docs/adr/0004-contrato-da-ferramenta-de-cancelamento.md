# ADR-0004 — Cancelamento aceita código ou área+data, uma reserva por chamada, e nunca age sob ambiguidade

**Status:** aceito
**Data:** 2026-11-08
**Origem:** [`docs/spike-1.1-dominio-invariantes.md`](../spike-1.1-dominio-invariantes.md) → `dominio/D-03` e `dominio/D-04`
**Invariantes e garantias afetados:** `I-02`, `I-06`; Garantia 2 do enunciado; regra de negócio 4
**Relacionado:** ADR-0001 (cancelar escreve `ativa = 0` na tabela que aquele ADR define)

> As duas decisões de origem foram registradas juntas porque descrevem **o mesmo contrato**: como a ferramenta de cancelamento é invocada e como se comporta. Separadas, nenhuma das duas fica legível — saber que a ferramenta aceita código não diz o que acontece quando o pedido é ambíguo.

## Contexto

No Residencial Aurora, o morador cancela as próprias reservas conversando pelo chat. A regra de negócio 4 do enunciado define o cancelamento de forma peculiar: *"o morador pode cancelar **as reservas** do próprio apartamento, **sem confirmação**"*.

Duas coisas nessa frase decidem o contrato.

**O plural não é esclarecido.** Não se diz se um único pedido pode cancelar várias reservas. O roteiro do avaliador cancela uma por vez, mas o enunciado avisa que ele "pode variar a redação das mensagens" — então *"cancela minhas reservas"* é uma frase que pode chegar.

**A ausência de confirmação é o que pesa.** Reservar área com taxa e autorizar visitante exigem aprovação explícita do morador por uma rota própria da API. Cancelar, não: executa direto. Isso remove a única oportunidade de o morador rever a ação antes que ela aconteça — e o cancelamento é irreversível no que importa, porque a data liberada pode ser tomada por outro apartamento no instante seguinte.

Há ainda uma restrição de isolamento. O passo 4 do roteiro do avaliador pede, numa sessão do apartamento 101, o cancelamento de uma reserva que pertence ao **302**, e verifica que o código dessa reserva alheia não apareça **nem na resposta nem no histórico de eventos da sessão**.

## Decisão

A ferramenta de cancelamento:

1. **Aceita as duas formas de identificar a reserva** — o par `(area, data)` ou o `codigo` —, e **valida o dono em ambos os caminhos**. O apartamento vem do state da sessão, nunca de parâmetro escolhido pelo modelo.
2. **Cancela exatamente uma reserva por chamada.** Para cancelar várias, o modelo chama várias vezes.
3. **Não age sob ambiguidade.** Se o pedido não identifica uma única reserva, **nada é executado** e o assistente pergunta qual. Isso não é a confirmação da Garantia 1 — é esclarecimento antes de existir ação definida, não aprovação de ação já formada.
4. **A resposta nomeia o que foi cancelado** — área e data.

Quando um código não pertence ao apartamento da sessão, a ferramenta **não distingue, na resposta, "é de outro apartamento" de "não existe"**. As duas situações produzem o mesmo resultado.

## Alternativas consideradas

- **Aceitar apenas `(area, data)`.** Era a recomendação do spike, por tornar o vazamento do passo 4 estruturalmente impossível — código alheio nunca entraria no fluxo. Rejeitada por ser artificial: o morador que acabou de ver a própria lista de reservas tem o código à mão, e recusar essa forma de pedir não ajuda ninguém. O custo de aceitar é que a validação de dono deixa de ser opcional.
- **Ferramenta de cancelamento em lote.** Resolveria "cancela tudo" numa chamada. Rejeitada porque combina mal com a ausência de confirmação: um pedido ambíguo poderia apagar mais do que o morador queria, sem nada interpondo-se, e sem reversão.

## Consequências

**O que fica mais fácil:** o morador pede do jeito que lhe for natural, citando código ou área e data. Cada cancelamento é um efeito isolado e auditável no histórico de eventos, nunca um apagamento em massa.

**O que fica mais difícil, ou passa a custar atenção:** a validação de dono vira obrigatória em dois caminhos em vez de um. E a resposta precisa ser **deliberadamente ambígua** quando o código não é do morador — se distinguir "não é seu" de "não existe", a ferramenta vira um oráculo que confirma a existência de reservas alheias, violando a segunda cláusula da Garantia 2. É um ponto onde a implementação óbvia (mensagem de erro informativa) é a errada.

Além disso, "cancele todas" passa a custar N chamadas ao modelo, com o custo de quota que isso implica.

**Risco aceito:** a detecção de ambiguidade depende do agente, não de código. Um modelo pode decidir que *"cancela minha reserva"* se refere à única que lhe parece relevante e chamar a ferramenta com argumentos definidos — e a ferramenta não tem como saber que o pedido original era ambíguo. A mitigação é a instrução do agente, que é justamente o tipo de garantia frágil que este projeto evita; aceita-se porque a alternativa (ferramenta recusando quando há mais de uma reserva possível) exigiria que ela conhecesse o texto do pedido, que ela não recebe.

## Verificação

| Cenário | Protege | Tipo |
|---|---|---|
| Cancelar citando o código da própria reserva | a decisão deste ADR | positivo |
| Cancelamento informa explicitamente o que foi cancelado | a decisão deste ADR | positivo |
| Cancelar citando o código de uma reserva de outro apartamento | `I-02`, `I-06` | **regressão** — falha se a validação de dono sumir, ou se a resposta distinguir "não é seu" de "não existe" |
| Escopo de escrita | `I-02` | **regressão** |
| Pedido de cancelamento ambíguo não executa nada | a decisão deste ADR | positivo |
| Cancelar reserva que não existe | a decisão deste ADR | positivo |

Arquivo: `tests/features/reservas.feature`

## Onde isso vive no código

| O quê | Onde |
|---|---|
| Cancelar por `(area, data)` | `app/infra/repositorio_postgres.py` → `cancelar_reserva_por_area_data` |
| Cancelar por `codigo`, validando o dono | `app/infra/repositorio_postgres.py` → `cancelar_reserva_por_codigo` |
| Devolve a reserva cancelada (área e data) | `app/infra/repositorio_postgres.py` → `_cancelar` |
| Código alheio ≡ código inexistente | `app/dominio/erros.py` → `ReservaNaoEncontrada` |

⚠️ A validação de dono é o `apartamento` no `WHERE`, não um `if` depois da
consulta: código de outro apartamento simplesmente não casa, e o chamador
recebe a **mesma** exceção de "não existe". Distinguir os dois casos
transformaria a ferramenta num oráculo sobre reservas alheias (I-06).

Parte verificada: 3 cenários `@storage` verdes em `tests/features/reservas.feature`.
Pendentes os `@conversa` (ambiguidade e redação da resposta), que dependem da Fase 4.
