# ADR-0003 — A ferramenta valida a área em runtime, contra a tabela de áreas

**Status:** aceito
**Data:** 2026-11-08
**Origem:** [`docs/spike-1.1-dominio-invariantes.md`](../spike-1.1-dominio-invariantes.md) → `dominio/D-02`
**Invariantes e garantias afetados:** nenhum invariante próprio
**Relacionado:** ADR-0002 (cria a tabela contra a qual se valida)

## Contexto

O Residencial Aurora permite ao morador reservar áreas comuns pelo chat. **Três** áreas são reserváveis: salão de festas, churrasqueira e quadra.

Mas o condomínio tem outras áreas comuns, e o morador convive com elas. O regulamento interno, que o próprio assistente consulta para tirar dúvidas, lista no Art. 4º, IV: academia, brinquedoteca, playground — e dedica um capítulo inteiro à piscina. Nada impede que o morador escreva *"reserve a piscina para sábado"*, e o enunciado do desafio **não diz** o que deve acontecer nesse caso: o comportamento é escolha nossa.

Um modelo de linguagem conduzindo a conversa torna isso mais provável, não menos — ele pode inferir que "piscina" é uma área válida por analogia com as outras, ou inventar um identificador plausível como `"piscina"` ou `"area-piscina"`.

## Decisão

A ferramenta de reserva recebe a área como **string livre** e a valida em runtime **contra a tabela de áreas** (a mesma que o ADR-0002 semeia e que `reserva.area` referencia).

Área inexistente produz um retorno estruturado de erro contendo **a lista das áreas que podem ser reservadas**, para que o modelo reformule o pedido sem precisar adivinhar.

A validação é da **ferramenta**, não do prompt: nenhuma instrução ao agente é responsável por impedir área inválida.

## Alternativas consideradas

- **Restringir o tipo do parâmetro** (`Literal["salao-de-festas", "churrasqueira", "quadra"]`), de modo que a declaração enviada ao modelo já limite os valores aceitos. Rejeitada por duas razões: não foi verificado que o ADK 2.14.0 impõe isso de fato, e um valor fora da lista produziria erro de validação cru em vez de uma resposta útil ao morador.
- **As duas combinadas** — tipo restrito como primeira barreira e validação em runtime como rede. Era a recomendação do spike; ficou para depois, se o desperdício de turnos se mostrar relevante na prática. Pode ser adotada sem alterar esta decisão, porque a validação continua existindo por baixo.

## Consequências

**O que fica mais fácil:** qualquer grafia que o modelo invente produz uma resposta compreensível ao morador, com as opções válidas. A validação vive num lugar só e vale para todos os caminhos — reservar, consultar disponibilidade, cancelar.

**O que fica mais difícil, ou passa a custar atenção:** o modelo chega a chamar a ferramenta com um valor inválido antes de ser corrigido, o que gasta um turno e uma chamada ao modelo. Isso importa porque o avaliador executa dezenas de chamadas e um dos passos dispara aprovações concorrentes — estourar quota vira erro de servidor.

**Risco aceito:** o custo de um turno desperdiçado por pedido inválido. Aceito porque a alternativa que o evitaria (`Literal`) não está verificada, e porque pedidos de área inexistente devem ser raros no fluxo real — o avaliador não os exercita.

## Verificação

| Cenário | Protege | Tipo |
|---|---|---|
| Reservar área que não existe falha | a decisão deste ADR | positivo |

Arquivo: `tests/features/reservas.feature`

**Nota sobre cenário de regressão:** este ADR não declara invariante, e a alternativa rejeitada (`Literal`) produziria o **mesmo resultado observável** — a reserva não é criada nos dois casos. A diferença está em quantos turnos se gasta até lá, que nenhum teste de comportamento alcança. Não há cenário de regressão a escrever, e isso significa que a decisão é reversível sem quebrar nada observável: adotar `Literal` depois é mudança aditiva.

## Onde isso vive no código

| O quê | Onde |
|---|---|
| Validação antes de gravar | `app/infra/repositorio_postgres.py` → `criar_reserva`, primeiras linhas |
| Validação na consulta de disponibilidade | `app/infra/repositorio_postgres.py` → `data_esta_livre` |
| Ferramenta que traduz a recusa | `app/agentes/ferramentas/reservas.py` |
| Lista de áreas válidas na recusa | `app/dominio/erros.py` → `AreaInexistente.areas_validas` |

> **Correção de 2026-11-08.** Esta decisão esteve **implementada pela metade** desde que foi aceita: a validação entrou em `criar_reserva` e foi **esquecida** em `data_esta_livre`. Na prática, perguntar se a piscina estava livre devolvia `True` — o morador ouvia que uma área inexistente estava disponível. Encontrado pelo spike 1.6 (achado 4) e corrigido no P1 do plano 1.3, com cenário de regressão.

O cenário `@conversa` segue **pendente**: ele depende do
agente para transformar a recusa em resposta ao morador (Fase 4).
