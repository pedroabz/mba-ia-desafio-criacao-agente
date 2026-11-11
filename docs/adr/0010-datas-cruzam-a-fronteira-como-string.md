# ADR-0010 — As ferramentas recebem data como `str` e convertem internamente

**Status:** aceito
**Data:** 2026-11-08
**Origem:** [`docs/spike-1.3-superficie-de-tools.md`](../spike-1.3-superficie-de-tools.md) → `superficie/D-01`
**Invariantes e garantias afetados:** nenhum invariante; afeta toda ferramenta que recebe data
**Relacionado:** ADR-0011 (o que acontece quando a conversão falha)

## Contexto

No Residencial Aurora, o morador reserva áreas comuns e autoriza visitantes conversando por chat. Cinco das sete ferramentas do assistente recebem uma data, e o contrato da API usa o formato `AAAA-MM-DD`.

O que o modelo envia ao chamar uma ferramenta é sempre texto. A pergunta é onde esse texto vira uma data: o Google ADK pode fazer a conversão a partir da anotação de tipo da função, ou a ferramenta pode recebê-la como `str` e converter ela mesma.

O detalhe que decide isso foi verificado por execução: **a conversão automática do ADK está desligada por padrão.** O recurso `FUNCTION_TOOL_ARG_VALIDATION` é `EXPERIMENTAL` com `default_on=False` (`features/_feature_registry.py:196`). Anotar o parâmetro como `date` sem ligar o recurso não converte nada — a função recebe a string, e qualquer código que espere um `date` quebra na primeira operação.

## Decisão

As ferramentas declaram o parâmetro como **`data: str`** e fazem a conversão para `date` logo na entrada, antes de qualquer uso.

A anotação diz a verdade sobre o que chega. A conversão é explícita, e o erro de data malformada é tratado como recusa de negócio (ADR-0011), não como exceção escapando.

## Alternativas consideradas

- **Anotar como `date` e ligar `FUNCTION_TOOL_ARG_VALIDATION`.** Daria conversão automática e uma declaração mais expressiva para o modelo. Rejeitada porque faz o comportamento das ferramentas depender de uma variável de ambiente: o passo 1 do roteiro do avaliador monta o ambiente a partir do `.env.example`, e se a variável faltar o sistema **degrada em silêncio** — a anotação deixa de valer e a função passa a receber `str` onde espera `date`. Garantia que depende de configuração externa não é garantia.
- **Anotar como `date` sem ligar o recurso.** É o que parece certo e não funciona. Registrado porque é o erro provável de quem vier depois "melhorar as anotações".

## Consequências

**O que fica mais fácil:** o comportamento não depende de configuração. Qualquer clone, com ou sem `.env` completo, converte do mesmo jeito. A data malformada tem um ponto de tratamento previsível.

**O que fica mais difícil, ou passa a custar atenção:** cinco conversões explícitas em vez de zero, e a declaração enviada ao modelo diz apenas "string" — sem `format: date`, o modelo tem uma pista a menos sobre o formato esperado. A docstring precisa compensar, dizendo `AAAA-MM-DD`.

**Risco aceito:** o modelo pode enviar data em outro formato (`20/04/2030`, `20 de abril`). A conversão falha e vira recusa de negócio, que o modelo lê e pode corrigir numa segunda tentativa — ao custo de um turno. Não foi medido com modelo real com que frequência isso ocorre.

## Verificação

| Cenário | Protege | Tipo |
|---|---|---|
| Data em formato válido é aceita e grava a reserva no dia certo | a decisão deste ADR | positivo |
| Data malformada vira recusa, não erro de servidor | a conversão explícita | **regressão** — falha se alguém trocar por anotação `date` sem ligar o recurso |

Arquivo: `tests/features/ferramentas.feature`

## Onde isso vive no código

| O quê | Onde |
|---|---|
| Conversão e recusa de data malformada | `app/agentes/ferramentas/_comum.py` → `converter_data`, `DataInvalida` |
| Parâmetro declarado como `str` | as cinco ferramentas que recebem data |

Verificado por 2 cenários em `tests/features/ferramentas.feature`, ambos verdes.
