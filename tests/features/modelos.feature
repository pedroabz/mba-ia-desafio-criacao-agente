# language: pt
# Origem: docs/spike-2.4-modelos-gemini.md (Fase 2.4), via consolidate-spike
# ADRs: 0017 (um modelo nos quatro agentes) · 0018 (retry no 429, sem
#       FallbackModel) · 0019 (erro de quota vira 503)
# Restrições do spike: M-1, M-2, M-4, M-7
#
# TODOS pendentes: nenhum LlmAgent existe neste repositório (Fase 4) e a rota
# POST /sessoes/{id}/mensagens é da 3.2. Falham de propósito — cenário pulado é
# invisível, e invisível é perdido. Nunca apagar.
#
# NENHUM destes cenários precisa de chave de API, e isso é raro o bastante para
# valer o registro. Os quatro @estrutura inspecionam a árvore de agentes
# montada. Os cinco restantes precisam de um endpoint que responda 429 — o stub
# de scratchpad/spike24/h1_quota.py —, não do Gemini.
#
# MARCADOR: os dois cenários de 429 que exercitam o caminho do modelo usam
# @runner. Eles estiveram em @conversa por falta de marcador melhor, e isso era
# uma mentira registrada: a descrição de @conversa diz "com chave de API
# configurada", e aqui um stub local basta. @runner foi criado para dizer a
# verdade — "passa pelo runner do ADK, mas sem gastar API" — e para devolver
# estes cenários ao filtro do que roda sem chave, de onde nunca deviam ter
# saído. O cenário de retomada em Postgres (persistencia.feature) migrou junto.

Funcionalidade: Escolha de modelo, quota e erro do modelo

  # ADR-0017 · REGRESSÃO da decisão: a Opção A foi escolhida justamente pela
  # uniformidade — comportamento igual nos quatro agentes, para que problema de
  # roteamento não se confunda com diferença de modelo. A alternativa rejeitada
  # (dois Flash-Lite, dois baldes de quota) é observável exatamente aqui.
  # Falha no dia em que alguém dividir os agentes em dois modelos sem ADR.
  @estrutura
  Cenário: Os quatro agentes declaram o mesmo modelo
    Dado o aplicativo montado com o agente principal e os três especialistas
    Quando eu percorro todos os agentes da árvore
    Então os quatro declaram exatamente o mesmo nome de modelo
    E esse nome é o que a configuração do projeto define num lugar só

  # ADR-0017 · REGRESSÃO de M-1 · texto transportado do spike 2.4 (§ Cenários),
  # com o "todos terminam em -flash-lite" mantido: a decisão A o torna mais
  # forte, não mais fraco.
  # Falha se alguém "melhorar" o modelo do principal. 20 requisições por dia
  # contra 70-85 de uma correção: o modelo melhor é o que reprova.
  @estrutura
  Cenário: Nenhum agente usa um modelo da família Flash
    Dado o aplicativo montado com o agente principal e os três especialistas
    Quando eu percorro todos os agentes da árvore
    Então nenhum deles usa um modelo cujo nome case com "gemini-<n>.<n>-flash"
    E todos usam um modelo cujo nome termina em "-flash-lite"

  # ADR-0017 · REGRESSÃO de M-2 · texto transportado do spike 2.4.
  # LlmAgent.DEFAULT_MODEL é 'gemini-3.5-flash' (verificado em execução), que
  # roteia para gemini-3.8-flash — o balde de 20/dia. Agente sem model= cai
  # nele CALADO: não dá erro, não dá aviso. É por isso que o cenário olha a
  # declaração, não o valor efetivo.
  @estrutura
  Cenário: Nenhum agente herda o modelo padrão do ADK
    Dado o aplicativo montado com o agente principal e os três especialistas
    Quando eu percorro todos os agentes da árvore
    Então cada um declara explicitamente o seu modelo
    E nenhum modelo declarado é igual ao padrão do ADK

  # ADR-0017 · M-7, que até aqui NÃO TINHA NADA que a protegesse.
  # Medido no spike (achado 13): o ValueError do LLMRegistry só pega nomes que
  # não começam com "gemini-". 'gemini-9.9-inexistente' e até 'gemini-' são
  # ACEITOS na construção do agente e resolvem para a classe Gemini. O erro
  # aparece na PRIMEIRA CHAMADA, com 404 — isto é, no meio da conversa do
  # avaliador, com a correção em andamento.
  # Este cenário existe para que erro de digitação falhe na suíte, de graça e
  # sem chave, em vez de falhar no curl de quem está corrigindo o trabalho.
  # A LISTA tem conteúdo decidido: apenas `gemini-3.5-flash-lite` e
  # `gemini-3.1-flash-lite`, e nada mais. Ela recusa de propósito os modelos
  # SEM plano gratuito (`gemini-4-argon`), e é isso que faz este cenário
  # proteger DUAS restrições em vez de uma: a `M-7` (nome digitado errado é
  # aceito na construção e só quebra no primeiro 404) e a `M-3` (a chave é do
  # avaliador, então nada pode depender de tier pago). Modelo fora do plano
  # gratuito não falharia por digitação: falharia na correção de quem não paga.
  # Quem escreve a lista é a implementação, num lugar só, junto da configuração.
  @estrutura
  Cenário: O modelo de cada agente é um nome de modelo conhecido
    Dado o aplicativo montado com o agente principal e os três especialistas
    Quando eu percorro todos os agentes da árvore
    Então o modelo de cada um está na lista de modelos Gemini conhecidos do projeto

  # ADR-0018 · texto transportado do spike 2.4 (§ Cenários), ajustado: a
  # decisão B ficou valendo, então o cenário deixou de ser condicional.
  # Medido (caso D do harness h1_quota.py): com o padrão do ADK, um 429
  # ISOLADO — pico de RPM, não quota diária — derruba o turno inteiro com UMA
  # requisição, porque o SDK devolve stop_after_attempt(1) quando
  # retry_options é None (_api_client.py:677-678).
  @runner
  Cenário: Um 429 transitório não derruba o turno
    Dado um modelo que recusa a primeira requisição com 429 e aceita a segunda
    Quando o morador envia uma mensagem
    Então ele recebe uma resposta normal
    E foram feitas duas requisições ao endpoint do modelo

  # REGRESSÃO · ADR-0018 · é a observação que separa esta decisão da
  # alternativa "não fazer nada": o número de tentativas.
  # ⚠️ E protege a armadilha do initial_delay: o SDK IGNORA o retryDelay que o
  # servidor manda (medido: 3 tentativas em 0,17 s com initial_delay baixo).
  # A espera é escolha nossa; baixá-la para "deixar o teste rápido" mantém
  # attempts=3 e transforma a mitigação em três recusas em sequência — sem
  # nenhum teste ficar vermelho. Daí a asserção sobre a espera configurada.
  @runner
  Cenário: Um 429 persistente produz três tentativas ao modelo, não uma
    Dado um modelo que recusa toda requisição com 429
    Quando o morador envia uma mensagem
    Então foram feitas três requisições ao endpoint do modelo
    E a espera inicial configurada entre as tentativas é de ao menos 2 segundos

  # ⚠️ REGRESSÃO · ADR-0019 · M-4 · É O CENÁRIO MAIS IMPORTANTE DESTE ARQUIVO.
  # Pelo contrato do enunciado, "resposta" vazia significa "parei esperando
  # confirmação". Uma rota que monta a resposta com o texto dos eventos e PARA
  # no primeiro evento de erro devolve 200 {"resposta": ""} — e uma falha de
  # quota se disfarça de confirmação pendente que nunca existiu.
  # Não é hipótese: foi o que o primeiro harness do spike fez, e ele concluiu
  # com convicção que o ADK engolia o 429 em silêncio. O raise do ADK está
  # DEPOIS do yield (_finalizer.py:579), então fechar o gerador antes engole o
  # erro. Falha no dia em que alguém "otimizar" a drenagem do gerador.
  @api
  Cenário: Quota esgotada nunca vira resposta vazia
    Dado um modelo que recusa toda requisição com 429
    Quando o morador envia uma mensagem
    Então a rota NÃO responde 200 com "resposta" vazia
    E nenhuma confirmação pendente é publicada nessa resposta

  # ADR-0019 · o lado positivo da decisão: a falha de quota tem assinatura
  # própria, distinguível de confirmação pendente (200 vazio) e de bug (500).
  # 503 não está no contrato do enunciado — o ganho é de qualidade, e o
  # cabeçalho é o que diz "volte depois" em vez de "tem bug aqui".
  @api
  Cenário: Quota esgotada responde 503 com Retry-After
    Dado um modelo que recusa toda requisição com 429
    Quando o morador envia uma mensagem
    Então a rota responde 503
    E a resposta traz o cabeçalho Retry-After

  # REGRESSÃO · ADR-0019 · texto transportado do spike 2.4 (§ Cenários).
  # Não é desejo: é o que o ADK já faz (achado 6) — o Runner emite o evento e
  # ele FICA GRAVADO na sessão, junto da mensagem do morador. Os passos 12 e 13
  # do roteiro inspecionam e CONTAM os eventos, então isso não pode ser
  # surpresa. Falha se alguém passar a filtrar eventos de erro da sessão para
  # "limpar" a resposta de GET /sessoes/{id}/eventos.
  @api
  Cenário: O evento de erro do modelo fica visível na sessão
    Dado um modelo que recusa toda requisição com 429
    Quando o morador envia uma mensagem
    E eu consulto GET /sessoes/{id}/eventos
    Então existe um evento com error_code "RESOURCE_EXHAUSTED"
