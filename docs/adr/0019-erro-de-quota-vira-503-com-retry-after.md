# ADR-0019 — Erro de quota vira `503` com `Retry-After`, e a rota drena o gerador de eventos de propósito

**Status:** aceito
**Data:** 2026-11-08
**Origem:** [`docs/spike-2.4-modelos-gemini.md`](../spike-2.4-modelos-gemini.md) → `modelos/D-03`
**Invariantes e garantias afetados:** nenhum invariante do domínio. Protege a **leitura da Garantia 1** no contrato da API: `resposta` vazia significa *"parei esperando confirmação"*, e esta decisão impede que uma falha de modelo produza esse mesmo sinal.
**Relacionado:** ADR-0011 (recusa de negócio nunca vira erro de servidor — **o caso oposto**, ver abaixo) · ADR-0018 (o retry que tenta evitar chegar aqui) · ADR-0013 (quem publica `confirmacoes_pendentes`, o campo que esta decisão protege de ambiguidade)

## Contexto

O contrato do enunciado para `POST /sessoes/{id}/mensagens` é `200` com `{"resposta", "confirmacoes_pendentes": []}`, e a `resposta` **pode ser vazia quando o fluxo parou esperando confirmação**. Essa cláusula é o que torna esta decisão necessária.

A medição mostrou que um erro de quota chega ao `Runner` **de duas formas**, e isso não é redundância — são dois caminhos que o código consome de maneiras diferentes:

1. **Um evento** com `error_code='RESOURCE_EXHAUSTED'`, `error_message` com o link de mitigação do ADK mais o corpo do `429`, e `content` vazio. Esse evento **fica gravado na sessão**: o harness contou dois eventos persistidos — a mensagem do morador e o erro. Logo ele aparece em `GET /sessoes/{id}/eventos`, que os passos 12 e 13 do roteiro inspecionam e **contam**.
2. **Uma exceção** `_ResourceExhaustedError` — mas **só se o consumidor drenar o gerador**. Em `google/adk/flows/llm_flows/core/_finalizer.py:579`, o `raise model_error` acontece **depois** do `yield` do evento. Quem para no primeiro evento de erro fecha o gerador antes do `raise` e não vê exceção nenhuma.

O modo de falha ruim é específico, e a investigação provou que ele é fácil de cometer: **o primeiro harness escrito para este spike caiu nele**, parando no evento de erro e concluindo — com convicção — que o ADK engolia o `429` em silêncio. Em código de produção o mesmo erro produz `200 {"resposta": "", "confirmacoes_pendentes": []}`.

É aí que a restrição **`M-4`** entra: a rota **não pode** responder `200` com `resposta` vazia por causa de erro do modelo, porque resposta vazia é, pelo contrato, o sinal de *"parei esperando confirmação"*. Uma falha de quota se disfarçaria de pendência inexistente, e o avaliador leria "sem capacidade" como "pendência criada".

**Distinção do ADR-0011, que é vizinho e aponta para o outro lado.** Lá, recusa de negócio — área ocupada, visitante duplicado, código inexistente — **nunca** pode virar erro de servidor: ela é resposta normal, porque a regra do condomínio funcionou. Falta de quota **não é** recusa de negócio: é **indisponibilidade**. Tratá-la como recusa mentiria para o morador sobre a regra do condomínio — "não foi possível reservar" quando a reserva nunca foi tentada. Os dois ADRs não se contradizem: um proíbe `500` para o que é regra, o outro proíbe `200` para o que é falha de infraestrutura.

## Decisão

**Um erro de quota do modelo é traduzido em `503`, com o cabeçalho `Retry-After`.** O caminho é um `exception handler` para o erro do cliente Gemini com `code == 429`.

**E a rota `POST /sessoes/{id}/mensagens` drena o gerador de eventos até o fim, de propósito** — porque é a única forma de a exceção existir. Essa drenagem é **parte da decisão**, não detalhe de implementação: ela precisa estar escrita e **comentada citando `M-4`**, para que ninguém a "otimize" de volta para um `break` no primeiro evento de erro.

O evento com `error_code='RESOURCE_EXHAUSTED'` **permanece** gravado na sessão. Não há tentativa de limpá-lo: é o que o ADK já faz, e é informação verdadeira sobre o que aconteceu naquele turno.

## Alternativas consideradas

- **Deixar a exceção propagar, virando `500`.** O `exception handler` do FastAPI responde sozinho, sem uma linha nossa; é honesto, alto, e **respeita a `M-4` do mesmo jeito** — impossível confundir com confirmação pendente. Rejeitada pela mensagem, não pelo mecanismo: entre `500` e `503`, o segundo diz *"volte depois"* e o primeiro diz *"tem bug aqui"*, e para quem está corrigindo o trabalho essa diferença conta. É a alternativa aceitável, e o custo de trocar para ela é apagar um handler.
- **`200` com um texto de indisponibilidade no campo `resposta`.** Ficaria dentro do contrato (`200`, `404`, `409`) e o morador receberia texto em vez de erro cru. **Eliminada pela `M-4`**: é o modo de falha disfarçado de sucesso — qualquer verificação automática, inclusive o nosso script da Fase 5, vê `200` e segue. É o mesmo defeito do `@skip` que a regra 3 do `CLAUDE.md` proíbe: desaparecer em silêncio. E texto fabricado pelo código no campo onde o modelo escreve embaralha quem disse o quê. **Fica registrada porque é o caminho que um código escrito sem pensar nisso produz sozinho** — não é uma opção que alguém defenda, é a que acontece por omissão.

## Consequências

**O que fica mais fácil:** a falha de quota passa a ter **assinatura própria**, distinguível de confirmação pendente (`200` com `resposta` vazia) e de bug (`500`). Quem lê o log, o `curl` ou a saída do script da Fase 5 sabe o que aconteceu sem abrir a sessão. E o caso fica demonstrado no README, que é entregável avaliado.

**O que fica mais difícil, ou passa a custar atenção:** `503` **não está no contrato** do enunciado, que define `200`, `404` e `409` — é código a mais, que o avaliador não testa; o ganho é de qualidade, não de nota. E a dependência invertida: a rota **tem de drenar** o gerador para que a exceção chegue ao handler. Um `break` no evento de erro — que parece uma otimização razoável e passa em qualquer revisão desatenta — devolve silenciosamente o `200` vazio que a `M-4` proíbe. Daí o comentário obrigatório no código e o cenário de regressão.

**Risco aceito:** o handler captura por `code == 429` do cliente Gemini, o que o acopla ao formato do erro do SDK. Se uma versão futura mudar a classe ou o atributo, o erro volta a propagar como `500` — degradação para a alternativa A, que é aceitável, mas silenciosa. Aceita-se porque o cenário de regressão abaixo cobre o que importa (`200` vazio nunca acontece), e porque o modo de falha é o caminho honesto, não o disfarçado.

## Verificação

| Cenário | Protege | Tipo |
|---|---|---|
| Quota esgotada nunca vira resposta vazia | `M-4` — **o cenário mais importante deste conjunto** | **regressão** — falha no dia em que a rota voltar a parar no primeiro evento de erro |
| Quota esgotada responde 503 com `Retry-After` | a decisão deste ADR | positivo |
| O evento de erro do modelo fica visível na sessão | o que o ADK já faz, e que os passos 12 e 13 contam | **regressão** — falha se alguém passar a filtrar eventos de erro da sessão |

Arquivo: `tests/features/modelos.feature`

Os três rodam **sem chave de API**: precisam de um endpoint que responda `429`, não do Gemini.

## Onde isso vive no código

| O quê | Onde |
|---|---|
| O `exception handler` que traduz `429` em `503` + `Retry-After` | `app/api/aplicacao.py`, na fábrica da aplicação |
| A drenagem explícita do gerador de eventos, comentada citando `M-4` | `app/api/rotas/sessoes.py` → a rota `POST /sessoes/{id}/mensagens` |

**As duas peças que sustentam esta decisão, e nenhuma funciona sozinha:**

| O quê | Onde |
|---|---|
| Drenar os events até o fim, para a exceção existir (`A-7`) | `app/api/conversa.py` → `_rodar` |
| Traduzir em `503` com `Retry-After` | `app/api/erros.py` → `registrar_tratadores` |
| Reconhecer o erro de quota na cadeia de causas | `app/api/erros.py` → `e_erro_de_quota` |

⚠️ **Não ponha `break` no laço de events de `_rodar`.** É o que torna a
exceção alcançável: o `raise` do ADK está **depois** do `yield`. Quem para no
evento de erro não vê exceção nenhuma, monta resposta vazia e devolve `200` —
que é, pelo contrato, o sinal de "parei esperando confirmação". A falha de
quota se disfarçaria de pendência (`M-4`).

Verificado por 3 cenários `@api` em `tests/features/modelos.feature`, contra um
stub HTTP que responde `429` — **sem gastar quota de verdade**.

Quando a rota for escrita, o comentário da drenagem é obrigatório e precisa
dizer **por quê**, citando `M-4` e este ADR: o `raise` do ADK está depois do
`yield` (`_finalizer.py:579`), então parar no evento de erro troca uma falha
visível por um `200` com `resposta` vazia — que é o sinal de confirmação
pendente. Foi exatamente o erro que o primeiro harness do spike 2.4 cometeu.
