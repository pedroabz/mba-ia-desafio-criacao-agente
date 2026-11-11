# Plano: as seis ferramentas de domínio e o portão de confirmação

**Status:** executado em 2026-11-08
**Origem:** [`docs/spike-1.3-superficie-de-tools.md`](spike-1.3-superficie-de-tools.md), consolidado em 2026-11-08
**Implementa:** ADR-0010, ADR-0011, ADR-0012, ADR-0013 — e completa o ADR-0003

---

## O que este plano constrói

O **Residencial Aurora** é um assistente de condomínio exposto por uma API: o morador conversa por chat e reserva áreas comuns, cancela reservas e autoriza visitantes. Um avaliador corrige rodando 15 passos contra a API.

**Hoje não existe nenhuma ferramenta de agente neste projeto.** Nenhuma. O diretório `app/agentes/` está vazio desde a montagem do repositório.

O que existe e está **em uso** é a camada abaixo delas:

| Em uso hoje | O quê |
|---|---|
| `app/infra/repositorio_sqlite.py` | criar, cancelar (duas formas), listar, autorizar, consultar disponibilidade — tudo com o apartamento como argumento explícito |
| `app/dominio/erros.py` | as recusas de negócio, já distinguindo `AreaIndisponivel` de `JaReservadaPorVoce` |
| banco, schema, seed, comandos | plano 1.1, executado |

Este plano constrói a **camada que falta entre o modelo e o repositório**: as seis ferramentas que o assistente poderá chamar, com as assinaturas que os ADRs fixaram, e o portão que decide quando uma ação exige confirmação do morador.

Quando terminar, as ferramentas existem e são chamáveis — ainda sem agente que as hospede, o que é a Fase 4.

## O que fica de fora

| Não entra | Por quê |
|---|---|
| **`buscar_no_regulamento`** | A assinatura é saída do [plano 1.4](plano-1.4-postgres-e-recuperacao-semantica.md), que ainda está em rascunho. |
| **`on_tool_error_callback`** | O ADR-0011 manda registrá-lo **em cada agente** — e nenhum agente existe. Entra na Fase 4. Este plano entrega a outra metade do ADR: o `except` local onde a recusa carrega dado aproveitável. |
| **Projeção de `detalhes` por lista branca** | É a metade do ADR-0013 que vive na **camada da API**, e depende da rota de confirmações (3.2), bloqueada. Este plano entrega a outra metade: o portão que decide se confirma. |
| **Os agentes** | Fase 4. |

## Passos

### P1 — `consultar_disponibilidade` deixa de mentir sobre área inexistente

**Implementa:** completa o ADR-0003
**Depende de:** —
**Entrega:** validação de área em `data_esta_livre` (`app/infra/repositorio_sqlite.py`), levantando `AreaInexistente` como `criar_reserva` já faz.

**Pronto quando:** fica verde `Consultar disponibilidade de área inexistente não responde livre`.

**Risco:** —

> **Por que é o primeiro passo e não parte do P3.** É **bug em código já escrito**, não ferramenta nova: o ADR-0003 decidiu validar a área em runtime, a validação foi implementada em `criar_reserva` e **esquecida** aqui. Hoje `data_esta_livre("piscina", …)` devolve `True` — o morador que perguntar pela piscina ouve que está livre. Separado porque não depende de nada e pode ser corrigido e verificado sozinho.

---

### P2 — O portão de confirmação

**Implementa:** ADR-0013 (a metade que lê a taxa)
**Depende de:** —
**Entrega:**
- retrato imutável das taxas, carregado da tabela de áreas na subida da aplicação
- a função que `require_confirmation` consulta, decidindo pela taxa da área
- autorização de visitante decide `True` sempre

**Pronto quando:** ficam verdes
- `Reservar área com taxa aciona o portão de confirmação`
- `Reservar área sem taxa não aciona o portão`
- `Autorizar visitante sempre aciona o portão`

**Risco:** a função recebe **os mesmos argumentos da ferramenta, inclusive `tool_context`** — verificado no spike R1, onde omiti-lo levantou `TypeError` em tempo de execução. E o spike 1.3 mediu que ela é invocada **4×** por reserva aprovada; se levantar exceção durante a retomada, a ação nunca executa.

---

### P3 — As quatro ferramentas de reserva

**Implementa:** ADR-0010, ADR-0011, ADR-0012
**Depende de:** P1 (a disponibilidade precisa estar correta), P2 (o portão)
**Entrega:**
- `consultar_disponibilidade(area, data)` → só `{livre}` — nunca o dono, nunca o código
- `listar_minhas_reservas()` → dicionário nomeado, só ativas, só do apartamento da sessão
- `criar_reserva(area, data)` → passa pelo portão
- `cancelar_reserva_por_area_e_data(area, data)` e `cancelar_reserva_por_codigo(codigo)` — duas ferramentas, parâmetros obrigatórios
- data recebida como `str` e convertida na entrada
- `except` local para `AreaInexistente` e `JaReservadaPorVoce`

**Pronto quando:** ficam verdes os 9 cenários de reserva listados na tabela abaixo.

**Risco:** o invariante **I-06** vive inteiro no `return` destas ferramentas, e não tem mecanismo que o force — um `return` descuidado o quebra sem erro. É o ponto onde o cenário substitui o mecanismo, e por isso dois dos nove são de regressão sobre exatamente isso.

---

### P4 — As duas ferramentas de visitante

**Implementa:** ADR-0010, ADR-0011
**Depende de:** P2
**Entrega:**
- `listar_meus_visitantes()` → dicionário nomeado, só do apartamento da sessão
- `autorizar_visitante(nome, data)` → passa pelo portão, grava, traduz a colisão em recusa

**Pronto quando:** ficam verdes `Listar os próprios visitantes devolve só os do apartamento da sessão` e `Autorizar visitante grava e recusa a duplicata`.

**Risco:** —

---

### P5 — Fechar o rastro

**Implementa:** —
**Depende de:** P1–P4
**Entrega:** *Onde isso vive no código* preenchido em ADR-0010, 0011, 0012, 0013; ADR-0003 anotado com a correção do P1.

**Pronto quando:** `uv run python scripts/cobertura.py` não acusa ponteiro quebrado.

**Risco:** —

## Cenários que este plano faz virar

| Cenário | Passo |
|---|---|
| Consultar disponibilidade de área inexistente não responde livre | P1 |
| Reservar área com taxa aciona o portão de confirmação | P2 |
| Reservar área sem taxa não aciona o portão | P2 |
| Autorizar visitante sempre aciona o portão | P2 |
| Data em formato válido grava a reserva no dia certo | P3 |
| Data malformada vira recusa, não erro | P3 |
| Recusa de negócio não escapa como exceção | P3 |
| Área inexistente informa que não é reservável | P3 |
| Consultar data ocupada não revela o dono | P3 |
| Cancelar citando área e data cancela a reserva certa | P3 |
| Cancelar citando o código cancela a reserva certa | P3 |
| Cancelar código de outro apartamento não altera nada nem confirma a existência | P3 |
| Listar as próprias reservas devolve só as do apartamento da sessão | P3 |
| Listar as próprias reservas não traz reserva cancelada | P3 |
| As listagens devolvem um dicionário nomeado, não uma lista crua | P3 |
| Listar os próprios visitantes devolve só os do apartamento da sessão | P4 |
| Autorizar visitante grava e recusa a duplicata | P4 |

**17 cenários**, todos em `tests/features/ferramentas.feature`.

**Continuam vermelhos**, e por quê:

| Cenário | Por quê | Destrava com |
|---|---|---|
| `Argumento inventado pelo modelo não aparece nos detalhes da pendência` | é a metade do ADR-0013 que vive na API | rota de confirmações (3.2) |
| Os 7 `@recuperacao` | dependem de `buscar_no_regulamento` | plano 1.4 |
| Os 17 `@conversa` e 4 `@estrutura` | dependem dos agentes | Fase 4 |

## Ordem e paralelismo

**P1 e P2 são independentes entre si** e podem ir em qualquer ordem — o bug da disponibilidade e o portão não se tocam.

**P3 depende dos dois.** Da disponibilidade porque `consultar_disponibilidade` a envolve e herdaria a mentira; do portão porque `criar_reserva` passa por ele.

**P4 depende só de P2.** Pode ir em paralelo com P3, se houver dois pares de mãos.

P5 é fechamento.

## Riscos do plano

- **As ferramentas precisam de um `ToolContext` para serem testadas**, porque é dele que sai o apartamento da sessão (`I-02`). Os 17 cenários chamam as ferramentas diretamente, sem agente — montar esse contexto de teste é a parte menos óbvia do trabalho, e subestimá-la atrasa todos os passos de uma vez.
- **`I-06` fica inteiro sob disciplina até a Fase 5.** Nenhum mecanismo força a projeção do retorno. Os cenários são a única rede, e só pegam o que alguém pensou em escrever.
- **O ADR-0011 fica pela metade.** Sem `on_tool_error_callback`, uma exceção inesperada de um caminho não previsto ainda viraria 500 — a rede que o ADR descreve só existe quando houver agente. Até lá, vale o `except` local, que cobre o que foi previsto e nada além.

## Validação

- [x] Revisado e aprovado — 2026-11-08
- [x] Executado — 2026-11-08. Os 17 cenários declarados ficaram verdes; nenhum cenário não declarado mudou de cor.
