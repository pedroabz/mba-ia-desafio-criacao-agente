# language: pt
# Origem: docs/spike-1.4-estrategia-regulamento.md (Fase 1.4) e, nos três
#         últimos cenários, docs/spike-2.4-modelos-gemini.md → modelos/D-04
# ADRs: 0015 (recuperação semântica) · 0008 (Regulamento é AgentTool) ·
#       0016 (por artigo, devolvendo lista) · 0020 (modelo de embedding,
#       task_type e 768 dimensões) · 0021 (até 3 artigos, corte 0,65)
#
# ✅ Os LIMIARES foram medidos e fixados: ADR-0021 — até 3 artigos, com corte
# absoluto de 0,65 de similaridade de cosseno. Os valores antigos citados aqui
# eram da busca LÉXICA e não transferiam; foram substituídos pelos medidos
# contra os 96 artigos reais, em 2026-11-08.
#
# @pendente = ainda não implementado, FALHA de propósito. Nunca apagar.

Funcionalidade: Consulta ao regulamento interno

  # ADR-0015 · passo 12 do avaliador. A resposta está no Art. 22, II —
  # "aos domingos e feriados, das 9h às 20h".
  @recuperacao
  Cenário: A dúvida da piscina aos domingos recupera o trecho que a responde
    Quando busco no regulamento por "até que horas a piscina funciona aos domingos"
    Então o trecho devolvido contém o horário de fechamento aos domingos

  # REGRESSÃO · ADR-0015 · É O MOTIVO DA DECISÃO. As palavras "horas",
  # "cachorro" e "barulho" têm ZERO ocorrências no documento; o método léxico
  # errava exatamente aqui. Falha se a recuperação voltar a comparar palavras.
  @recuperacao
  Esquema do Cenário: Pergunta com vocabulário divergente recupera o trecho certo
    Quando busco no regulamento por "<pergunta>"
    Então o trecho devolvido vem do <capitulo>

    Exemplos:
      | pergunta                            | capitulo                        |
      | posso ter cachorro no apartamento   | Capítulo VIII — Animais         |
      | quanto barulho posso fazer de noite | Capítulo III — Silêncio         |
      | onde guardo meu carro               | Capítulo XI — Garagem           |

  # ⚠️ REGRESSÃO · ADR-0016 e ADR-0022 · É A RAZÃO DE RECUPERAR POR ARTIGO E
  # EM LISTA. Verificado no documento: o Art. 39 (Cap. VI, salão) manda
  # "respeitar o período de silêncio previsto no Capítulo III" e NÃO DÁ O
  # HORÁRIO; quem dá é o Art. 16 (Cap. III): "entre 22h e 8h". NENHUM DOS DOIS
  # RESPONDE SOZINHO.
  #
  # ⚠️ ESTE CENÁRIO FICOU VERMELHO NA PRIMEIRA IMPLEMENTAÇÃO, e o que ele
  # revelou virou o ADR-0022. A busca por similaridade devolvia Art. 39, 17 e
  # 37 — o Art. 16 não aparecia nem no top 8. A causa é a própria decisão do
  # ADR-0016: o título do capítulo entra no vetor, então os 8 artigos do
  # "Capítulo VI: Salão de festas..." casam com qualquer pergunta que diga
  # "salão" e enterram o artigo de outro capítulo que tem a resposta. A mesma
  # decisão que faz a piscina funcionar causava isto.
  #
  # A correção foi seguir a REMISSÃO EXPLÍCITA: o Art. 39 cita o Capítulo III
  # por escrito, e a frase da remissão, usada como consulta restrita àquele
  # capítulo, traz o Art. 16 com 0,8114. Medido — e a frase funciona porque
  # nomeia o conceito ("o período de silêncio"), que é o que o Art. 16 define.
  #
  # Falha de novo se alguém desligar o seguimento de remissão (verificado por
  # sabotagem: derruba exatamente este cenário) ou voltar a devolver um trecho
  # só. O ADR-0021 fixou o teto em 3 artigos, e a vaga da remissão sai de
  # dentro dele: o recorte não cresceu.
  @recuperacao
  Cenário: Pergunta cuja resposta exige dois artigos recupera os dois
    Quando busco no regulamento por "posso fazer festa com som no salão até 2h"
    Então a lista devolvida contém o Art. 39
    E a lista devolvida contém o Art. 16
    E a lista devolvida não contém o capítulo inteiro de nenhum dos dois

  # ⚠️ REGRESSÃO · ADR-0016 · O CASO MAIS REVELADOR, e o argumento mais forte
  # contra recuperar por capítulo. Verificado: a resposta é o Art. 56, que
  # está no Cap. VIII (Animais). O Cap. VI, sobre a quadra, tem ZERO menções
  # a animais nos seus 8 artigos.
  # Recuperando por CAPÍTULO, "quadra" traria o Cap. VI — que não responde —
  # e o capítulo certo nem apareceria no topo. A resposta mora onde o morador
  # nunca consultaria.
  @recuperacao
  Cenário: A resposta está num capítulo que a pergunta não menciona
    Quando busco no regulamento por "meu cachorro pode ir na quadra"
    Então a lista devolvida contém o Art. 56
    E o Art. 56 trata de animais em áreas comuns
    E nenhum trecho do Capítulo VI é devolvido como resposta principal

  # ⚠️ REGRESSÃO · ADR-0021 · I-05 · Garantia 4 · É O CENÁRIO QUE SUSTENTA O
  # CORTE, e o modo de falha que mais importa: devolver um trecho arbitrário em
  # vez de admitir que não achou. "Achei errado" chega ao morador como
  # resposta; "não achei" o modelo contorna.
  # MEDIDO contra os 96 artigos reais: estas três perguntas têm como melhor
  # resultado 0,5595 / 0,5710 / 0,5980 — todas abaixo do corte de 0,65 do
  # ADR-0021, e todas com os três primeiros colocados quase empatados (0,37%
  # de diferença no caso do bitcoin), porque nenhum artigo tem a ver com a
  # pergunta. Foi esse empate que derrubou a alternativa do corte RELATIVO.
  # Falha se alguém tirar o corte: aí "quanto custa o bitcoin" passa a
  # responder "Art. 62 — Mudanças".
  @recuperacao
  Esquema do Cenário: Pergunta fora de escopo não devolve trecho nenhum
    Quando busco no regulamento por "<pergunta>"
    Então nenhum trecho é devolvido
    E a resposta informa que o assunto não está no regulamento

    Exemplos:
      | pergunta                    |
      | quanto custa o bitcoin hoje |
      | qual o telefone da pizzaria |
      | oi, tudo bem?               |

  # REGRESSÃO · ADR-0021 · I-05 · Garantia 4 · o teto existe para que uma
  # pergunta vaga não traga meio documento, que é o custo que a Garantia 4
  # evita. O NÚMERO está decidido: no máximo 3 artigos (ADR-0021). Com a
  # mediana de 472 caracteres por artigo, 3 artigos são ~1,4 mil caracteres
  # contra os 44 mil do documento — folga enorme sobre "um quinto".
  @recuperacao
  Cenário: O recorte nunca devolve o regulamento inteiro
    Quando busco no regulamento por "regras do condomínio"
    Então o trecho devolvido é menor que um quinto do documento

  # REGRESSÃO · Garantia 4 · passo 12 · os três marcadores abaixo são únicos
  # no documento e exclusivos de capítulos que tratam de OUTROS assuntos.
  # Asserção por palavra genérica daria falso positivo: o próprio Cap. IV
  # fala de "animais de qualquer espécie".
  @recuperacao
  Cenário: O recorte da piscina não arrasta capítulos de outros assuntos
    Quando busco no regulamento por "até que horas a piscina funciona aos domingos"
    Então o trecho devolvido não contém "coleira refletiva"
    E não contém "plástico bolha"
    E não contém "lona xadrez"

  # REGRESSÃO · ADR-0008 + ADR-0016 · a topologia isola o trecho recuperado,
  # mas NÃO a resposta do especialista — ela volta como function_response na
  # sessão principal. É a política de citação que fecha a Garantia 4.
  @conversa
  Cenário: A resposta cita o artigo sem colar o capítulo
    Dado uma sessão do 101
    Quando o morador pergunta até que horas a piscina funciona aos domingos
    Então a resposta traz o horário de fechamento
    E a resposta cita o artigo de origem
    E nenhum evento da sessão contém o texto integral do capítulo consultado

  # ADR-0016 · a válvula: sob pedido explícito, o especialista transcreve.
  # O limite é O ARTIGO, nunca o capítulo — e a recuperação por artigo torna
  # isso seguro por construção: não existe caminho que cole 3 KB.
  @conversa
  Cenário: Sob pedido, o especialista transcreve o artigo — e só ele
    Dado uma sessão do 101
    E que o morador já perguntou sobre o horário da piscina
    Quando ele pede "me mostra o texto exato dessa regra"
    Então a resposta contém o texto do artigo citado
    E nenhum evento da sessão contém o texto integral do capítulo

  # REGRESSÃO · ADR-0016 · a válvula NÃO pode virar o caminho padrão: sem
  # pedido explícito, a resposta é prosa curta.
  @conversa
  Cenário: Sem pedido, a resposta não transcreve o regulamento
    Dado uma sessão do 101
    Quando o morador pergunta até que horas a piscina funciona aos domingos
    Então a resposta não contém o texto integral de nenhum artigo

  # ───────────────────────────────────────────────────────────────────────────
  # Os três cenários abaixo vêm de modelos/D-04 (spike 2.4) e são verificados
  # pelo ADR-0020. Nenhum precisa de chave de API: observam o SCHEMA gravado e
  # o PARÂMETRO enviado ao cliente de embedding, nunca a qualidade do vetor —
  # que é propriedade do modelo, não do nosso código.
  # Quem os faz virar verde é o passo P4 do plano 1.4.
  # ───────────────────────────────────────────────────────────────────────────

  # REGRESSÃO · ADR-0020 · M-6 · o padrão do modelo é 3.072 dimensões, e
  # vector(3072) grava e consulta mas NÃO ACEITA índice hnsw nem ivfflat (o
  # pgvector para em 2.000). Para 96 artigos a varredura exata é instantânea,
  # então o que 768 preserva é OPÇÃO FUTURA, não desempenho hoje — e um quarto
  # do espaço por vetor.
  # Falha no dia em que alguém "simplificar" para a dimensão padrão.
  @storage
  Cenário: A coluna de vetor do regulamento tem 768 dimensões
    Dado o schema do banco aplicado
    Então a coluna de embedding da tabela de trechos do regulamento tem 768 dimensões
    E gravar um vetor de dimensão diferente é recusado pelo banco

  # ADR-0020 + ADR-0016 (unidade = artigo) · é o critério de pronto do P4 do
  # plano 1.4, que até esta consolidação apontava para um cenário inexistente.
  # A última asserção não é zelo: é a armadilha M-5 em forma de teste. Com o
  # gemini-embedding-2, passar os artigos como lista de strings devolve UM
  # vetor agregado — a média semântica do regulamento inteiro — sem erro
  # nenhum, e a busca passa a responder sempre a mesma coisa. A decisão do
  # ADR-0020 (gemini-embedding-001) mata essa restrição; a asserção fica para
  # o dia em que alguém migrar de modelo.
  @storage
  Cenário: O seed do regulamento grava um vetor para cada artigo
    Dado o regulamento de dados/regulamento.md
    Quando a restauração é executada
    Então existe um trecho gravado para cada artigo do regulamento
    E cada trecho gravado tem o seu próprio vetor, com 768 dimensões
    E nenhum vetor gravado é idêntico ao de outro trecho

  # ⚠️ REGRESSÃO · ADR-0020 · É A RAZÃO DA DECISÃO, e não é qualidade de vetor:
  # para ~96 artigos curtos os candidatos acertam ou erram pelos mesmos
  # motivos. O desempate foi que task_type é PARÂMETRO verificável em código,
  # enquanto no gemini-embedding-2 o tipo de tarefa é PREFIXO DE TEXTO NO
  # PROMPT — e num projeto cuja tese é que regra em prompt não conta, o
  # mecanismo que o código controla é o coerente.
  # Este cenário é o que torna essa frase verificável. Falha se a assimetria
  # desaparecer ou voltar a ser prefixo de prompt.
  # Marcador: @storage por ser a camada mais baixa que ainda prova o ponto —
  # um cliente de embedding de teste registra o parâmetro, sem modelo, sem
  # chave e sem precisar dos 96 vetores que @recuperacao exigiria.
  @storage
  Cenário: Semear usa RETRIEVAL_DOCUMENT e buscar usa RETRIEVAL_QUERY
    Dado um cliente de embedding que registra o task_type de cada chamada
    Quando a restauração gera os vetores do regulamento
    E uma pergunta do morador é convertida em vetor para a busca
    Então a chamada que gerou os vetores dos artigos usou task_type "RETRIEVAL_DOCUMENT"
    E a chamada que converteu a pergunta usou task_type "RETRIEVAL_QUERY"

  # ⚠️ REGRESSÃO · ADR-0020 · BUG REAL, encontrado ao executar o P4 do plano
  # 1.4. O `google-genai` lê a chave de `os.environ`, e NADA neste projeto
  # copiava o `.env` para lá — a configuração afirmava, por escrito, que não
  # precisava. Resultado: com uma chave válida no arquivo, `aurora-restaurar`
  # recusava dizendo que não havia chave. E o passo 1 do roteiro do avaliador
  # é exatamente "copie o .env.example, preencha a sua chave, restaure".
  #
  # O bug era invisível porque a mensagem de erro era PLAUSÍVEL: quem a lesse
  # conferiria o arquivo, veria a chave lá, e não teria pista do que fazer.
  #
  # O cenário monta o seu próprio arquivo em vez de ler o `.env` da máquina:
  # a suíte não pode depender de quem a roda ter uma chave.
  @storage
  Cenário: A chave do .env chega a quem gera os embeddings
    Dado um arquivo de ambiente com a chave do Gemini preenchida
    Quando a configuração é lida desse arquivo
    Então a chave chega à configuração
    E o cliente de embedding é construído com ela, sem recusar por falta de chave
