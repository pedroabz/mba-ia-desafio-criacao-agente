# ADR-0011 — Recusa de negócio chega ao modelo por `on_tool_error_callback`, e nunca escapa como exceção

**Status:** aceito
**Data:** 2026-11-08
**Origem:** [`docs/spike-1.3-superficie-de-tools.md`](../spike-1.3-superficie-de-tools.md) → `superficie/D-02`
**Invariantes e garantias afetados:** Garantia 5 (recusa normal, nunca erro de servidor)
**Relacionado:** ADR-0010 (data malformada é uma dessas recusas)

## Contexto

O repositório do Residencial Aurora recusa operações por regra de negócio levantando exceções — `AreaIndisponivel`, `ReservaNaoEncontrada`, `VisitanteJaAutorizado` e outras, em `app/dominio/erros.py`. Elas existem porque toda uma categoria de recusa precisa interromper a gravação.

Quando essas exceções sobem através de uma ferramenta do agente, elas não param ali. Verificado por execução: **uma exceção que escapa de uma ferramenta propaga para fora de `runner.run_async`**, derruba o turno inteiro e a API responde **500**.

Isso colide diretamente com o enunciado. A Garantia 5 exige que, quando dois moradores disputam a mesma área, *"uma reserva vence e a outra é recusada com uma resposta normal, sem erro de servidor"* — e o passo 14 do roteiro do avaliador dispara duas aprovações simultâneas conferindo que **as duas respondem 200**.

E não é só a disputa: toda recusa de negócio chega por esse caminho. Cancelar reserva inexistente, autorizar visitante duplicado, pedir área que não existe — qualquer uma delas viraria 500 se escapasse.

## Decisão

Cada agente registra um **`on_tool_error_callback`**, que captura qualquer exceção de uma ferramenta e a converte em resposta estruturada para o modelo. É a rede que garante que **nada vire 500**, em qualquer caminho, inclusive os que ninguém previu.

Além disso, **onde a recusa carrega informação própria que melhora a resposta**, a ferramenta a trata localmente com `except`, para aproveitar o que a exceção já traz:

| Exceção | Por que vale tratar localmente |
|---|---|
| `AreaInexistente` | carrega a lista de áreas válidas, que impede o modelo de inventar outro id |
| `JaReservadaPorVoce` | carrega a reserva — e pode identificá-la, porque é do próprio morador |

Os dois mecanismos têm papéis diferentes e não se sobrepõem: o tratador por agente garante que nada escape; o `except` local existe onde há algo a dizer além de "recusado".

## Alternativas consideradas

- **Apenas `except` local em cada ferramenta.** Mais explícito, e a resposta ao modelo fica no mesmo lugar da chamada. Rejeitada como solução única porque depende de **lembrar em todas as ferramentas** — e uma exceção inesperada, de um caminho que ninguém previu, continuaria virando 500. Justamente a falha que a Garantia 5 proíbe.
- **Apenas o tratador por agente.** Suficiente para impedir o 500, mas descarta informação: a lista de áreas válidas e a identificação da própria reserva se perderiam numa mensagem genérica de erro.

## Consequências

**O que fica mais fácil:** o 500 por recusa de negócio deixa de ser possível, inclusive em caminhos não previstos. A disputa do passo 14 responde 200 nos dois lados por construção, não por tratamento específico.

**O que fica mais difícil, ou passa a custar atenção:** há dois lugares onde uma recusa pode ser tratada, e a leitura de "o que o modelo recebe" exige olhar os dois. A regra que mantém isso são: o `except` local só existe onde a exceção carrega dado aproveitável; nos demais casos, deixa subir para o tratador.

**Risco aceito:** o tratador por agente captura **qualquer** exceção, inclusive bug genuíno — um `AttributeError`, por exemplo, viraria uma recusa de negócio apresentada ao modelo em vez de um erro visível. Erro de programação passa a parecer regra de negócio. Mitigação: o tratador precisa registrar em log o que capturou, para que bug não se esconda atrás de recusa.

## Verificação

| Cenário | Protege | Tipo |
|---|---|---|
| Recusa de negócio não derruba a conversa | a decisão deste ADR | **regressão** — falha se uma exceção voltar a escapar do runner |
| Disputa de reserva responde normalmente aos dois moradores | Garantia 5, passo 14 | **regressão** |
| Área inexistente informa que não é reservável | o `except` local de `AreaInexistente` | positivo |

Arquivo: `tests/features/ferramentas.feature`

## Onde isso vive no código

| O quê | Onde |
|---|---|
| Tradução da recusa para o modelo | `app/agentes/ferramentas/_comum.py` → `recusa` |
| `except RecusaDeNegocio` em cada ferramenta | `reservas.py`, `visitantes.py` |
| Recusas que carregam dado aproveitável | `AreaInexistente` (áreas válidas), `JaReservadaPorVoce` (a própria reserva) |

✅ **A rede existe.** O `on_tool_error_callback` está registrado nos **três
especialistas** (`app/agentes/especialistas.py`), e o tratador vive em
`app/agentes/tratador_de_erro.py`. A metade que faltava era essa.

⚠️ **O risco aceito deste ADR está mitigado no código, e vale conferir se
alguém mexer:** o tratador captura **qualquer** exceção, inclusive bug
genuíno — um `AttributeError` viraria recusa apresentada ao modelo. A
mitigação é o `logger.exception` para o que não é `RecusaDeNegocio`. **Tirar
esse log faz bug se esconder atrás de recusa**, que é exatamente o que o ADR
aceitou de olhos abertos e só o log impede.

Refinamento que a implementação sugeriu: o `except` local ficou **mais amplo**
que o ADR descreve (captura toda `RecusaDeNegocio`, não só as que carregam
dado), porque sem agentes era a única forma de os cenários passarem. Quando o
tratador por agente existir, a divisão natural fica: **local** para recusa de
negócio, que é esperada; **callback** para o inesperado, que é bug.

Verificado por 3 cenários em `tests/features/ferramentas.feature`, todos verdes.
