# ADR-0005 — Autorizar a mesma pessoa para a mesma data duas vezes é recusado, com aviso ao morador

**Status:** aceito
**Data:** 2026-11-08
**Origem:** [`docs/spike-1.1-dominio-invariantes.md`](../spike-1.1-dominio-invariantes.md) → `dominio/D-01`
**Invariantes e garantias afetados:** nenhum invariante do enunciado; cria uma regra de unicidade própria
**Relacionado:** —

## Contexto

No Residencial Aurora, o morador autoriza pelo chat a entrada de visitantes. A regra de negócio 3 do enunciado define a autorização de forma fechada: *"autorizar um visitante libera a entrada de alguém no prédio. A autorização registra **o nome do visitante e a data da visita**."*

O registro, portanto, não tem identificador próprio: nos dados iniciais do condomínio ele é `{apartamento, nome, data}`, e a rota de verificação da API devolve apenas `{nome, data}`. A chave de negócio é a tripla.

O enunciado **não diz** o que acontece se o morador pedir *"libera a Joana no dia 21"* duas vezes. Ele enumera o que está fora de escopo, e este caso não está nessa lista — então o comportamento é escolha nossa, e ela muda o que a rota de verificação passa a devolver.

## Decisão

A segunda autorização para a mesma tripla `(apartamento, nome, data)` é **recusada**, e a resposta informa ao morador que aquela pessoa já está autorizada naquela data.

A unicidade é imposta por `UNIQUE (apartamento, nome, data)` na tabela de autorizações — não por verificação prévia na ferramenta.

## Alternativas consideradas

- **Permitir a duplicata.** Nenhum código, nenhum índice; a lista passaria a conter duas linhas idênticas. Rejeitada porque a rota de verificação exibiria a duplicata, o que fica confuso se um passo do roteiro de avaliação for repetido.
- **Tratar como idempotente** — a segunda chamada não cria linha nova e responde como sucesso. Era a recomendação do spike, por ser a única que não pode surpreender o avaliador: repetir um passo continuaria devolvendo `200` e a lista continuaria correta. Rejeitada em favor de informar o morador: entre devolver sucesso silencioso e dizer o que está acontecendo, escolheu-se dizer.

## Consequências

**O que fica mais fácil:** a lista de visitantes de um apartamento nunca contém duplicatas, e o morador descobre imediatamente que a pessoa já estava autorizada — em vez de supor que criou uma segunda autorização que não existe.

**O que fica mais difícil, ou passa a custar atenção:** se o roteiro de avaliação repetir um pedido de autorização esperando sucesso, receberá uma recusa. O passo 11 autoriza Joana Ribeiro uma única vez, então o risco não se materializa no fluxo conhecido — mas é um comportamento que diverge do "aprovar executa a ação uma única vez" da Garantia 1, que trata de confirmação repetida e não de pedido repetido. A distinção precisa ficar clara para quem implementar: **reenviar uma confirmação já respondida é 409 e não executa; pedir de novo a mesma autorização é uma recusa de negócio.**

**Risco aceito — e é o mais relevante deste ADR:** **nome não serve como chave de identidade.** Duas pessoas podem ter o mesmo nome, e aqui não há sequer exigência de sobrenome: "Joana" e "Joana" são indistinguíveis para o sistema. A consequência concreta é um **falso positivo** — se o morador precisar autorizar duas visitantes homônimas para a mesma data, a segunda será recusada indevidamente, e não há como contornar.

Isso é aceito porque o enunciado define a autorização como contendo exatamente nome e data, e porque o escopo é um exercício avaliado por um roteiro conhecido, onde o caso não ocorre. **Num sistema de produção a chave seria um documento (CPF) ou um identificador emitido no momento da autorização, e o nome seria apenas rótulo.** Acrescentar CPF aqui foi considerado e descartado: a regra 3 fecha o conteúdo do registro, a rota de verificação devolve só `{nome, data}` e não teria onde exibi-lo, e o passo 11 do avaliador autoriza "Joana Ribeiro" apenas pelo nome — exigir documento obrigaria o assistente a uma pergunta extra no meio desse fluxo, sem ganho.

## Verificação

| Cenário | Protege | Tipo |
|---|---|---|
| Autorizar a mesma pessoa duas vezes na mesma data é recusado | a decisão deste ADR | positivo |
| Após a recusa, o apartamento continua com exatamente uma autorização | a unicidade `(apartamento, nome, data)` | **regressão** — falha se o índice único sumir e a duplicata passar a ser gravada |

Arquivo: `tests/features/visitantes.feature`

## Onde isso vive no código

| O quê | Onde |
|---|---|
| `PRIMARY KEY (apartamento, nome, data)` | `app/infra/banco.py` → `DDL`, tabela `autorizacao_entrada` |
| Grava e traduz a colisão em recusa | `app/infra/repositorio_postgres.py` → `autorizar_visitante` |
| A recusa de negócio | `app/dominio/erros.py` → `VisitanteJaAutorizado` |

⚠️ A unicidade é do banco, não de uma consulta prévia: o método tenta gravar e
converte `IntegrityError` em recusa. Trocar por "consulta antes, grava depois"
abriria janela entre as duas operações.

Verificado por 2 cenários em `tests/features/visitantes.feature`, ambos verdes.
