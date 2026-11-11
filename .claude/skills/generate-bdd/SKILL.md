---
name: generate-bdd
description: "Extrair cenários de comportamento de qualquer arquivo markdown e materializá-los como arquivos .feature executáveis e PENDENTES — vermelhos na suíte até alguém implementá-los. Use sempre que houver comportamento descrito em documento que ainda não tem teste: 'gera os cenários desse spike', 'transforma esses BDDs em teste', 'cria os cenários pendentes', 'materializa os cenários', 'extrai os cenários desse md', 'quero que isso não se perca até a implementação', ou depois de qualquer spike/ADR que descreva comportamento esperado. Use também quando o pedido for em inglês ('generate the pending scenarios', 'turn these into feature files'). Gera .feature com etiqueta @pendente e steps que falham alto, nunca testes pulados."
---

# Gerar cenários pendentes

Transformar comportamento descrito em prosa ou Gherkin dentro de um markdown em **arquivos `.feature` executáveis**, etiquetados como pendentes e falhando na suíte até alguém implementá-los.

A regra que organiza tudo: **um cenário que não é executável é um cenário que vai se perder.** Documento se lê uma vez e some na pasta; suíte de teste se roda toda vez. A finalidade desta skill não é escrever teste bonito — é garantir que uma decisão tomada hoje continue sendo cobrada daqui a três semanas, por outra pessoa ou outro agente, sem que ninguém precise lembrar de abrir o documento.

Daí a consequência que não se negocia: **cenário não implementado nasce vermelho, nunca pulado.** Teste pulado é invisível, e invisível é o mesmo que perdido. Tem que aparecer na contagem e tem que incomodar.

## Entrada: qualquer markdown

Funciona com documento de spike, ADR, ata de reunião, anotação solta — qualquer arquivo que descreva comportamento esperado. Três situações, com tratamentos diferentes:

1. **Já tem Gherkin.** Transporte **literalmente**: mesmo texto, mesma ordem, mesmos nomes. Não "melhore" a redação — o texto do cenário é o contrato com quem escreveu, e divergência silenciosa entre documento e teste é precisamente o que se quer evitar.
2. **Tem prosa descrevendo comportamento** ("a ferramenta devolve só se a data está livre, nunca o dono"). Derive o cenário e **marque como derivado** no comentário, para quem revisar saber que a redação é sua, não da fonte.
3. **Tem decisão sem comportamento observável.** Não invente cenário. Registre no relatório que aquela decisão não produziu cenário e por quê — frequentemente significa que ela é reversível sem quebrar nada visível, o que é informação útil.

Quando o documento contiver invariantes numerados (`I-01`), decisões (`D-03`, ADRs) ou restrições (`C-2`), **cite a origem no comentário acima do cenário**. É o que permite, mais tarde, saber o que cada teste protege e descobrir órfãos nos dois sentidos.

## Duas etiquetas, sempre

**`@pendente`** — enquanto não há implementação. Sai quando o cenário passa de verdade; nunca é substituído por `@skip`.

**A camada**, que diz *quando* o cenário pode rodar:

| Etiqueta | Roda contra | Precisa de |
|---|---|---|
| `@storage` | o repositório/banco direto | nada além do schema |
| `@api` | as rotas HTTP | a aplicação no ar |
| `@conversa` | o agente respondendo | modelo configurado e chave de API |

A camada se infere do que o cenário observa: se o `Então` fala de linha gravada ou de lista devolvida pelo repositório, é `@storage`; se fala de código de status ou corpo de resposta HTTP, é `@api`; se depende de o assistente interpretar uma frase do usuário, é `@conversa`.

Na dúvida entre duas, **escolha a mais baixa que ainda prova o ponto**. Um cenário sobre exclusividade de reserva é `@storage`, mesmo que o morador chegue nele conversando: o que se quer provar é que o banco recusa, e provar isso sem subir modelo é mais rápido, mais barato e determinístico.

## Verifique efeito, não prosa

O erro mais caro nesta tradução é escrever asserção sobre o **texto** que o assistente produz. `Então a resposta informa que ele já tem essa reserva` é legítimo como enunciado de comportamento e péssimo como asserção: o modelo reformula a frase e o teste quebra sem nada ter regredido. Testes assim viram ruído, e teste ruidoso é desligado.

Ao materializar um `Então` que fala de resposta, traduza para algo estável:

- **estado depois** — o que ficou gravado, o que não ficou;
- **qual ferramenta foi chamada, com quais argumentos** — isso está nos eventos da sessão e é factual;
- **ausência de string proibida** — asserção negativa é robusta, porque não depende de como o modelo escreve;
- **presença ou não de confirmação pendente**.

Exemplo da tradução: *"o assistente pergunta qual reserva cancelar"* não vira comparação de frase. Vira **nenhuma ferramenta de cancelamento foi chamada** e **houve resposta ao morador**. Prova a mesma coisa e não quebra quando o modelo muda de palavra.

Quando o enunciado original realmente exigir conteúdo no texto (um horário, um valor que precisa aparecer), aí a asserção de conteúdo é legítima — mas prefira verificar o dado específico, não a frase inteira.

## Saída

**Cenários** em `tests/features/<tema>.feature`, agrupados **por tema do domínio** (`reservas.feature`, `visitantes.feature`, `sessao.feature`) e não por documento de origem. Um documento costuma atravessar vários temas, e arquivo por documento espalha o mesmo vocabulário de `Dado` por vários lugares. A rastreabilidade vem do comentário `# Origem:` acima de cada cenário, não do nome do arquivo.

```gherkin
# language: pt
# Origem: docs/spike-dominio-invariantes.md
Funcionalidade: <nome do agrupamento>

  # I-01 · dominio/D-06
  @pendente @storage
  Cenário: <texto literal da origem>
    Dado ...
    Quando ...
    Então ...
```

**Steps** em `tests/steps/test_<slug>.py`, um por cenário, falhando com mensagem legível:

```python
@scenario("../features/<slug>.feature", "<nome do cenário>")
def test_<nome>():
    """PENDENTE — origem: docs/<arquivo>.md · protege I-01"""

@given("...")
def _():
    raise NotImplementedError("PENDENTE: <nome do cenário>")
```

O que importa nessa forma é que `pytest` **colete e reporte** o cenário desde o primeiro dia. O runner é pytest-bdd; confirme a API da versão instalada antes de gerar, em vez de assumir.

**Antes de criar step novo, procure um existente.** Cenários do mesmo domínio repetem vocabulário — "Dado que o 101 tem a quadra reservada em X" aparece em vários. Reaproveitar mantém o conjunto pequeno: o custo real está nos primeiros cenários, e os seguintes tendem a só compor passos que já existem.

## Mesclar, nunca sobrescrever

Rodar a skill de novo sobre um documento atualizado **acrescenta**; não apaga. Cenário que já existe e não mudou fica como está, inclusive se já estiver verde — regenerar um cenário implementado o devolveria a `@pendente` e destruiria trabalho.

Se um cenário **sumiu** da origem, não o remova por conta própria: reporte, para a pessoa decidir. Cenário desaparecer de um documento costuma ser edição descuidada, não revogação deliberada — e apagar teste é exatamente o tipo de perda silenciosa que esta skill existe para impedir.

## Antes de terminar

Confira e relate:

- cada cenário da origem tem arquivo correspondente, ou está explicado por que não tem;
- nenhum cenário ficou sem etiqueta de camada;
- nenhum `@skip` foi usado em lugar de `@pendente`;
- `pytest --collect-only` enxerga todos os cenários novos — se não enxerga, eles não existem para efeito prático;
- a contagem: quantos cenários, quantos por camada, quantos derivados de prosa.

## Regras

- **Nada de `@skip`, `xfail` ou teste comentado.** São três formas de desaparecer em silêncio.
- **Cenário transportado é literal.** Reescrever o texto é perder o vínculo com o documento que o originou.
- **Cenário derivado de prosa vem marcado como derivado.**
- **Toda asserção sobre resposta de modelo vira asserção sobre efeito**, salvo quando o conteúdo é a exigência.
- **Não invente cenário para encorpar o arquivo.** Decisão sem comportamento observável se reporta, não se fantasia.
- **Não implemente o cenário aqui.** Esta skill materializa e deixa vermelho; fazer passar é trabalho da implementação.
