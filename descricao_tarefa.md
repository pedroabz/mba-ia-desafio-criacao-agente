1 - Criação de TODOs para tracking do que precisa ser feito
2 - Spikes para researchs a partir de skill criada
3 - Skill de ADRs para consolidar as decisões do projeto
4 - Skill para gerar cenários BDDs pendentes a serem depois validados por suite


Procedimento:
1 - Elaboração manual de uma TODO List daquilo que precisava ser feito para completar a tarefa baseada na descrição da tarefa na plataform fullcycle.
2 - Refinamento desse TODO manual com o readme através do Claude Code -> Geração do TODO.md presente do repositório
3 - Após alguma tentativa e erro, criamos 6 SKILLs para trabalhar na tarefa. O objetivo principal era tomar as decisões arquiteturais e levantar os cenários de teste para validação da tarefa. Além disso, algumas tarefas menores já poderiam ser feitas de antemão (como criação da API e do Banco de dados e seu seeding)
4 - As SKILLs foram: 
    - generate-spike: Recebe um número da tarefa TODO (1.1, 1.2, etc.) e executa um research (foi usado como base a SKILL de research do desafio do projeto ia mba greenfield)
    - Após tomadas as decisões arquiteturais / business, é rodada a skill consolidate-spike. Essa gera potencialmente três categorias de artefatos
        i - ADRs - Decisões de arquitura são consolidadas na pasta docs/adr
        ii - Cenários de teste de comportamento (BDD) - Consolidados em tests/features
        iii - Plano (exemplo: docs/plano-1.1-persistencia.md) - Quando há algo passível de já ser implementado, um plano é já gerado
        Obs importante: Se algum desses artefatos não é relevante na SPIKE, apenas não o fazemos (por exemplo, não há plano 1.2 pois essa foi uma tarefa puramente de definição de arquitura)
5 - Para cada plano executável, executamos a skill execute-plan