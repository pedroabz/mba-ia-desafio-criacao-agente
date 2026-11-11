# Residencial Aurora — instruções do projeto

Assistente virtual de condomínio: o morador conversa por chat e reserva áreas
comuns, cancela as próprias reservas, autoriza a entrada de visitantes e tira
dúvidas sobre o regulamento. Construído com **Google ADK** e exposto por uma
**API FastAPI**. É um desafio de MBA, corrigido por um avaliador que roda um
roteiro fixo de 15 passos contra a API (ver `README.md`, que é o enunciado).

A exigência central: **nenhuma mensagem do morador pode furar as regras do
condomínio.** Regra que mora no prompt não conta — uma mensagem bem escrita a
derruba. As regras moram no código.

## Como este projeto trabalha

```
generate-spike → você decide → consolidate-spike → você valida o plano → execute-plan
                               ↓ invoca generate-adr, generate-bdd, generate-plan
```

**Nada é implementado direto de um spike.** O caminho até o código passa por um
plano aprovado — é o gate que impede decisão tomada em silêncio dentro de uma
implementação.

| Onde | O quê |
|---|---|
| `TODO.md` | o plano, e o estado de cada etapa |
| `docs/spike-<id>-<slug>.md` | investigações. `<id>` bate com o item do `TODO.md` |
| `docs/adr/` | decisões tomadas, com o porquê e as alternativas rejeitadas |
| `tests/features/*.feature` | cenários que provam que as decisões continuam valendo |
| `docs/plano-<id>-<slug>.md` | planos de implementação, com status `rascunho`/`validado`/`executado` |
| `docs/planos/README.md` | **controle**: quais planos já foram executados e o que entregaram |
| `.claude/skills/` | as 6 skills da cadeia acima |

## Regras que não se negociam

**1. Nunca escreva em `dados/`.** São o estado inicial do condomínio. O
enunciado exige que fiquem byte-idênticos aos do repositório base e o passo 15
do avaliador confere. Leia à vontade; escrever é reprovação direta.

**2. Cenário `@pendente` nunca se apaga.** Ele marca comportamento que foi
decidido e ainda não implementado, e **falha de propósito** na suíte — cenário
pulado é invisível, e invisível é o mesmo que perdido. Implementar significa
remover a etiqueta do `.feature` e fazer passar. Remover um cenário exige um
ADR que explique por que ele deixou de valer.

**3. Nada de `@skip`, `xfail` ou teste comentado.** São três formas de
desaparecer em silêncio.

**4. ADR aceito não se reescreve.** Decisão revista vira ADR novo; o antigo é
marcado como substituído, com link para o sucessor. Apagar destrói a
informação mais útil do histórico: que aquele caminho já foi tentado.

**5. As regras duras são do banco, não do código.** O repositório grava e
traduz o erro em recusa de negócio; ele não "verifica antes para evitar o
erro". Entre uma verificação e a gravação cabe outra requisição — é a
Garantia 5, que o passo 14 do avaliador testa com duas aprovações simultâneas.

## Armadilhas já pagas

Coisas que já quebraram aqui. Não repita.

- **`AgentTool` mata a confirmação de tool, em silêncio.** A sessão aninhada é
  descartada, a pendência nunca aparece na API e a ação nunca executa, sem erro
  nenhum. Agente com tool que exige confirmação **precisa** ser `sub_agents`.
  Ver `docs/spike-R1-confirmacao-de-tools.md`, restrição R1.
- **`DatabaseSessionService` exige driver async.** Driver síncrono é recusado
  em tempo de construção; use `postgresql+asyncpg://`. E o pin precisa do
  extra: `google-adk[db]`.
- **Conexão do `asyncpg` fica presa ao event loop que a abriu.** Os passos do
  `pytest-bdd` são síncronos e cada um roda a sua corrotina num loop **novo** —
  com pool, o segundo passo de um cenário pega conexão de outro loop e morre
  com `got Future attached to a different loop`. Derrubou 29 cenários de uma
  vez. Por isso `criar_engine` usa `NullPool`; não "otimize" de volta. Ver
  ADR-0014.
- **O `.env` NÃO chega ao `os.environ`.** O `google-genai` lê a chave de lá, e
  nada a copia — então uma chave válida no arquivo era ignorada e
  `aurora-restaurar` recusava dizendo que não havia chave, no passo 1 do
  roteiro. Quem precisa da chave a recebe de `Configuracao.google_api_key`.
  Ver ADR-0020.
- **O índice de reserva é parcial.** `UNIQUE (area, data) WHERE ativa = 1`.
  Sem a cláusula, uma data cancelada fica bloqueada para sempre — e nenhum
  teste de reserva comum detecta. Ver ADR-0001.
- **Toda leitura de reserva filtra `ativa = 1`.** Esquecer em um lugar vaza
  reserva cancelada para a conversa.
- **Cancelar código alheio e código inexistente devolvem a MESMA recusa.**
  Distinguir transforma a ferramenta num oráculo sobre reservas de outros
  apartamentos. Ver ADR-0004.

## Comandos

```bash
uv sync                               # instala
docker compose up -d --wait           # sobe o Postgres com pgvector — PRIMEIRO
uv run aurora-restaurar               # restaura os dados e indexa o regulamento
uv run aurora-servir                  # sobe a API em http://localhost:8000
uv run pytest -q                      # suíte completa (pendentes falham: é o esperado)
uv run pytest -m storage              # só o que roda sem chave de API
uv run python scripts/cobertura.py    # acusa ADR/invariante/cenário órfão
docker compose down                   # para o banco, PRESERVANDO os dados
docker compose down -v                # para e APAGA os dados
```

**O banco vem antes de tudo** (ADR-0014). Sem ele, os cenários `@storage` e
`@api` falham e os dois comandos recusam com instrução — a mensagem diz qual
comando rodar, de propósito, porque o passo 1 do avaliador é num clone limpo.

**`aurora-restaurar` faz chamada de rede.** Ele gera os vetores do regulamento
pelo Gemini (ADR-0020), então exige `GOOGLE_API_KEY` no `.env`. São 96 artigos
em **uma** requisição; sem a chave, ele recusa antes de tocar o banco.

## Estilo

Código, comentários e documentos em **português**. Comentário explica *por
quê*, não *o quê* — e, quando houver um ADR ou invariante por trás, cita-o pelo
identificador (`ADR-0001`, `I-06`), para quem ler o código chegar à decisão.
