# CineData Analytics

Aplicação de análise de filmes por linguagem natural. O usuário faz uma pergunta
em português pela interface Streamlit e o sistema transforma a pergunta em uma
consulta somente leitura no SQLite, executa a consulta e apresenta os dados, um
gráfico opcional, a SQL gerada e o caminho percorrido pelos agentes.

## O que a aplicação faz

- Responde perguntas sobre filmes, bilheteria, finanças, popularidade,
  avaliações, gêneros, produtoras, elenco e equipe.
- Entende perguntas em linguagem natural em português.
- Exibe a resposta resumida, as linhas retornadas e um gráfico quando existe
  uma coluna numérica.
- Permite baixar o resultado em CSV.
- Mantém memória semântica das interações da sessão com Chroma.
- Mostra a SQL e as decisões dos agentes para facilitar a auditoria.
- Recusa perguntas fora do escopo do banco CineData.

Exemplos:

```text
Quais são os 10 filmes com maior receita em R$?
Qual a nota média por gênero?
Quantos filmes foram lançados por ano?
```

## Requisitos

- Python 3.11 ou superior.
- Uma chave da API do Groq. link: [https://groq.com/]
- (Opcional) Uma chave da API do Google Gemini.
- O arquivo SQLite `cinerocket.db`. Coloque na pasta "data" do diretório.

As chamadas aos modelos são externas e podem consumir cota ou estar sujeitas
ao limite de requisições do provedor. Nunca coloque chaves no código ou no
controle de versão.

## Instalação no Windows

Abra o PowerShell na raiz do projeto e crie o ambiente virtual:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Se o PowerShell bloquear a ativação, a política pode ser liberada somente para
o terminal atual:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

O projeto também pode ser executado sem ativar o ambiente, usando diretamente
`.venv\Scripts\python.exe` e `.venv\Scripts\streamlit.exe`.

## Configuração das chaves

Crie um arquivo `.env` na raiz do projeto. Ele é ignorado pelo Git:

```dotenv
GROQ_API_KEY=sua-chave-do-groq
GEMINI_API_KEY=sua-chave-do-google
# Opcional: por padrão usa data/cinerocket.db
# DB_PATH=C:\caminho\para\cinerocket.db
```

O código carrega as variáveis com `python-dotenv`. A variável `DB_PATH` é
opcional; se não for definida, o pipeline usa `data/cinerocket.db`.

## Como executar

Com o ambiente virtual ativo:

```powershell
streamlit run app/main.py
```

O Streamlit abrirá uma URL local, normalmente
`http://localhost:8501`. Digite uma pergunta, clique em **Analisar** e
aguarde o pipeline. A aba **Dados e gráfico** mostra o resultado, a aba
**SQL** mostra a consulta e a aba **Agentes** mostra as etapas e tentativas.

Para encerrar, pressione `Ctrl+C` no terminal.

## Como usar a interface

1. Escolha um exemplo na barra lateral ou escreva uma pergunta.
2. Clique em **Analisar**.
3. Consulte a resposta resumida e o status da execução.
4. Use **Baixar CSV** para exportar os dados.
5. Consulte **SQL** e **Agentes** quando precisar auditar a resposta.
6. Use **Limpar conversa** para remover o histórico e a memória semântica da
   sessão atual.

Os modelos gratuitos do Groq possuem limite de tokens por minuto. Se houver
erro de limite, aguarde alguns instantes antes de enviar outra pergunta.

## Arquitetura

```text
Streamlit (app/main.py)
        |
        v
Memória/histórico (services/memory_store.py)
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
Resultado estruturado (Pydantic) -> tabela, gráfico, CSV e auditoria
```

### Camadas

- **Interface:** `app/main.py` configura a página, recebe a pergunta e
  renderiza resposta, dados, SQL e etapas dos agentes.
- **Orquestração:** `src/graph/agents_graphs.py` define um `StateGraph` do
  LangGraph. O estado compartilhado contém pergunta, tentativa, SQL,
  validação, execução, resposta e erros.
- **Agentes:** `src/agents/agents_models.py` cria os clientes Groq e Gemini,
  prompts e parsers Pydantic.
- **Contrato de dados:** `src/schemas/structureds_outputs.py` define os
  modelos estruturados retornados pelos agentes.
- **Banco e regras de negócio:** `src/agents/schema_context.py` descreve
  tabelas, colunas, joins e regras financeiras usadas na geração da SQL.
- **Serviços:** `src/services/sql_executor.py` protege e executa consultas;
  `src/services/memory_store.py` persiste memória semântica por sessão.

## Fluxo dos agentes

1. **Reescritor de pergunta:** usa as duas interações mais recentes e até
   três memórias semanticamente relacionadas para transformar perguntas
   dependentes do contexto em uma pergunta independente. Na primeira pergunta
   da sessão, evita uma chamada desnecessária.
2. **Verificador:** decide se a pergunta pode ser respondida pelo CineData.
   Perguntas fora do escopo são rejeitadas sem consultar o banco.
3. **Gerador SQL:** recebe a pergunta independente e o contexto do schema e
   produz `objective`, `sql`, `category` e `explanation`.
4. **Validador SQL:** verifica coerência com o schema e segurança. Em caso de
   reprova, o grafo devolve o feedback ao gerador.
5. **Executor:** executa a consulta validada no SQLite e retorna colunas,
   linhas e quantidade de registros.
6. **Sintetizador:** recebe a consulta e no máximo 20 linhas do resultado e
   produz uma resposta curta em português.
    <img width="497" height="702" alt="cinedata_graph" src="https://github.com/user-attachments/assets/898928e5-c4e8-4421-8c4c-f77139316735" />

O grafo permite até três tentativas por pergunta. Falhas de validação ou
execução retornam ao gerador; ao atingir o limite, o fluxo termina com uma
mensagem de falha. Uma execução bem-sucedida é gravada na memória da sessão.

## Segurança do banco

O banco é tratado como fonte de dados somente leitura em duas camadas:

1. **Validação estrutural com SQLGlot:** `validate_readonly_sql` rejeita SQL
   vazia, palavras de escrita/DDL (`INSERT`, `UPDATE`, `DELETE`, `DROP`,
   `ALTER`, `CREATE`, `ATTACH`, `PRAGMA` e outras), múltiplas instruções
   encadeadas e qualquer raiz que não seja `SELECT`, `UNION` ou `WITH`.
2. **Conexão SQLite read-only:** o executor abre o arquivo com
   `mode=ro`, portanto a própria conexão recusa operações de escrita mesmo se
   uma consulta escapar da primeira validação.

Também existem limites operacionais:

- O resultado é limitado a 20 linhas por padrão.
- Um progress handler interrompe consultas que ultrapassem 35 segundos.
- O schema instrui os agentes a evitar joins caros na tabela
  `bridge_movie_person`.
- Erros de segurança, sintaxe ou execução são registrados no estado e exibidos
  na interface, sem transformar uma falha em resposta de sucesso.

Essa proteção reduz o risco de alteração do banco e de consultas abusivas,
mas não substitui controle de acesso, gerenciamento seguro das chaves,
isolamento de rede e revisão de consultas em um ambiente de produção.

## Memória e privacidade

As interações bem-sucedidas são persistidas em `chroma_memory/` com embeddings
multilíngues e metadados filtrados pelo `session_id`. O botão **Limpar
conversa** remove os registros associados à sessão atual. Como esse diretório
pode conter dados de conversas, ele está no `.gitignore` e não deve ser
publicado.

## Testes

Execute os testes da camada de SQL:

```powershell
pytest
```

Os testes cobrem consultas permitidas, bloqueio de comandos de escrita,
múltiplas instruções, literais com ponto e vírgula, limite de linhas, erros de
coluna e bloqueio de escrita pela conexão SQLite read-only.

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
    memory_store.py             # memória semântica Chroma
    sql_executor.py             # validação e execução segura
data/
  cinerocket.db                # banco local (não versionado)
tests/
  test_sql_executor.py
requirements.txt
pyproject.toml
```
