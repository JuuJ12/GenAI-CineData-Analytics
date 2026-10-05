# CineData Analytics

Aplicacao de analise de filmes por linguagem natural. O usuário faz uma pergunta
em português pela interface Streamlit e o sistema transforma a pergunta em uma
consulta somente leitura no SQLite, executa a consulta e apresenta os dados, um
grafico opcional, a SQL gerada e o caminho percorrido pelos agentes.

## O que a aplicacao faz

- Responde perguntas sobre filmes, bilheteria, financas, popularidade,
  avaliações, gêneros, produtoras, elenco e equipe.
- Entende perguntas em linguagem natural em português.
- Exibe a resposta resumida, as linhas retornadas e um gráfico quando existe
  uma coluna numerica.
- Permite baixar o resultado em CSV.
- Mantém memória semantica das interacoes da sessao com Chroma.
- Mostra a SQL e as decisões dos agentes para facilitar a auditória.
- Recusa perguntas fora do escopo do banco CineData.

Exemplos:

```text
Quais sao os 10 filmes com maior receita em R$?
Qual a nota media por genero?
Quantos filmes foram lancados por ano?
```

## Requisitos

- Python 3.11 ou superior.
- Uma chave da API do Groq. link: [https://groq.com/]
- (Opcional)Uma chave da API do Google Gemini para o agente de reescrita e sintese.
- O arquivo SQLite `cinerocket.db`. Coloque na pasta "data" do diretório.

As chamadas aos modelos sao externas e podem consumir cota ou estar sujeitas
ao limite de requisicoes do provedor. Nunca coloque chaves no codigo ou no
controle de versao.

## Instalação no Windows

Abra o PowerShell na raiz do projeto e crie o ambiente virtual:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Se o PowerShell bloquear a ativação, a politica pode ser liberada somente para
o terminal atual:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

O projeto tambem pode ser executado sem ativar o ambiente, usando diretamente
`.venv\Scripts\python.exe` e `.venv\Scripts\streamlit.exe`.

## Configuracao das chaves

Crie um arquivo `.env` na raiz do projeto. Ele e ignorado pelo Git:

```dotenv
GROQ_API_KEY=sua-chave-do-groq
GEMINI_API_KEY=sua-chave-do-google
# Opcional: por padrao usa data/cinerocket.db
# DB_PATH=C:\caminho\para\cinerocket.db
```

O código carrega as variaveis com `python-dotenv`. A variável `DB_PATH` e
opcional; se nao for definida, o pipeline usa `data/cinerocket.db`.

## Como executar

Com o ambiente virtual ativo:

```powershell
streamlit run app/main.py
```

O Streamlit abrira uma URL local, normalmente
`http://localhost:8501`. Digite uma pergunta, clique em **Analisar** e
aguarde o pipeline. A aba **Dados e gráfico** mostra o resultado, a aba
**SQL** mostra a consulta e a aba **Agentes** mostra as etapas e tentativas.

Para encerrar, pressione `Ctrl+C` no terminal.

## Como usar a interface

1. Escolha um exemplo na barra lateral ou escreva uma pergunta.
2. Clique em **Analisar**.
3. Consulte a resposta resumida e o status da execucao.
4. Use **Baixar CSV** para exportar os dados.
5. Consulte **SQL** e **Agentes** quando precisar auditar a resposta.
6. Use **Limpar conversa** para remover o historico e a memoria semantica da
   sessao atual.

Os modelos gratuitos do Groq possuem limite de tokens por minuto. Se houver
erro de limite, aguarde alguns instantes antes de enviar outra pergunta.

## Arquitetura

```text
Streamlit (app/main.py)
        |
        v
Memoria/historico (services/memory_store.py)
        |
        v
Grafo LangGraph (graph/agents_graphs.py)
        |
        +--> Verificador de escopo
        +--> Gerador de SQL
        +--> Validador de SQL
        +--> Executor SQLite somente leitura
        +--> Sintetizador da resposta
        |
        v
Resultado estruturado (Pydantic) -> tabela, grafico, CSV e auditoria
```

### Camadas

- **Interface:** `app/main.py` configura a pagina, recebe a pergunta e
  renderiza resposta, dados, SQL e etapas dos agentes.
- **Orquestracao:** `src/graph/agents_graphs.py` define um `StateGraph` do
  LangGraph. O estado compartilhado contem pergunta, tentativa, SQL,
  validacao, execucao, resposta e erros.
- **Agentes:** `src/agents/agents_models.py` cria os clientes Groq e Gemini,
  prompts e parsers Pydantic.
- **Contrato de dados:** `src/schemas/structureds_outputs.py` define os
  modelos estruturados retornados pelos agentes.
- **Banco e regras de negocio:** `src/agents/schema_context.py` descreve
  tabelas, colunas, joins e regras financeiras usadas na geracao da SQL.
- **Servicos:** `src/services/sql_executor.py` protege e executa consultas;
  `src/services/memory_store.py` persiste memoria semantica por sessao.

## Fluxo dos agentes

1. **Reescritor de pergunta:** usa as duas interacoes mais recentes e ate
   tres memorias semanticamente relacionadas para transformar perguntas
   dependentes do contexto em uma pergunta independente. Na primeira pergunta
   da sessao, evita uma chamada desnecessaria.
2. **Verificador:** decide se a pergunta pode ser respondida pelo CineData.
   Perguntas fora do escopo sao rejeitadas sem consultar o banco.
3. **Gerador SQL:** recebe a pergunta independente e o contexto do schema e
   produz `objective`, `sql`, `category` e `explanation`.
4. **Validador SQL:** verifica coerencia com o schema e segurança. Em caso de
   reprova, o grafo devolve o feedback ao gerador.
5. **Executor:** executa a consulta validada no SQLite e retorna colunas,
   linhas e quantidade de registros.
6. **Sintetizador:** recebe a consulta e no maximo 20 linhas do resultado e
   produz uma resposta curta em português.

O grafo permite ate três tentativas por pergunta. Falhas de validação ou
execucao retornam ao gerador; ao atingir o limite, o fluxo termina com uma
mensagem de falha. Uma execucao bem-sucedida e gravada na memoria da sessao.

## Seguranca do banco

O banco e tratado como fonte de dados somente leitura em duas camadas:

1. **Validacao estrutural com SQLGlot:** `validate_readonly_sql` rejeita SQL
   vazia, palavras de escrita/DDL (`INSERT`, `UPDATE`, `DELETE`, `DROP`,
   `ALTER`, `CREATE`, `ATTACH`, `PRAGMA` e outras), multiplas instrucoes
   encadeadas e qualquer raiz que nao seja `SELECT`, `UNION` ou `WITH`.
2. **Conexao SQLite read-only:** o executor abre o arquivo com
   `mode=ro`, portanto a propria conexao recusa operacoes de escrita mesmo se
   uma consulta escapar da primeira validacao.

Tambem existem limites operacionais:

- O resultado e limitado a 20 linhas por padrao.
- Um progress handler interrompe consultas que ultrapassem 35 segundos.
- O schema instrui os agentes a evitar joins caros na tabela
  `bridge_movie_person`.
- Erros de seguranca, sintaxe ou execucao sao registrados no estado e exibidos
  na interface, sem transformar uma falha em resposta de sucesso.

Essa protecao reduz o risco de alteracao do banco e de consultas abusivas,
mas nao substitui controle de acesso, gerenciamento seguro das chaves,
isolamento de rede e revisao de consultas em um ambiente de producao.

## Memoria e privacidade

As interacoes bem-sucedidas sao persistidas em `chroma_memory/` com embeddings
multilingues e metadados filtrados pelo `session_id`. O botao **Limpar
conversa** remove os registros associados a sessao atual. Como esse diretorio
pode conter dados de conversas, ele esta no `.gitignore` e nao deve ser
publicado.

## Testes

Execute os testes da camada de SQL:

```powershell
pytest
```

Os testes cobrem consultas permitidas, bloqueio de comandos de escrita,
multiplas instrucoes, literais com ponto e virgula, limite de linhas, erros de
coluna e bloqueio de escrita pela conexao SQLite read-only.

## Estrutura do projeto

```text
app/
  main.py                       # interface Streamlit
src/
  agents/
    agents_models.py            # clientes e agentes LLM
    schema_context.py           # contexto do banco para os prompts
  graph/
    agents_graphs.py            # grafo e estado do pipeline
  schemas/
    structureds_outputs.py      # modelos Pydantic
  services/
    memory_store.py             # memoria semantica Chroma
    sql_executor.py             # validacao e execucao segura
data/
  cinerocket.db                # banco local (nao versionado)
tests/
  test_sql_executor.py
requirements.txt
pyproject.toml
```
