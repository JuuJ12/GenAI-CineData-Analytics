

DB_SCHEMA_DESCRIPTION = """
Banco de dados: cinerocket.db (SQLite, acesso SOMENTE LEITURA).

TABELAS E COLUNAS:

dim_movies — um filme por linha
  sk_movie_id VARCHAR(64) PK
  titulo VARCHAR(500)
  data_lancamento DATE
  ano_lancamento INTEGER
  duracao_minutos INTEGER
  idioma_original VARCHAR(10)
  status_filme VARCHAR(50)   -- valores: 'Lançado', 'Em Produção', 'Planejado', 'Pós-Produção'
  sinopse VARCHAR(4000)

fact_movies_performance — métricas financeiras/popularidade (1 linha por filme, FK sk_movie_id -> dim_movies)
  orcamento_usd, receita_usd, lucro_usd NUMERIC   -- valores em DÓLAR
  orcamento_brl, receita_brl, lucro_brl NUMERIC   -- valores em REAL (BRL)
  popularidade DOUBLE
  nota_tmdb DOUBLE, qtd_tmdb INTEGER
  nota_imdb DOUBLE, qtd_imdb INTEGER

dim_reviews — nota agregada de usuários (1 linha por filme, FK sk_movie_id -> dim_movies)
  qtd_avaliacoes_usuarios INTEGER
  nota_media_usuarios DOUBLE   -- USE ESTA pra "nota dos usuários" (já é a média agregada)

movie_reviews — reviews individuais de usuários (N linhas por filme, FK sk_movie_id -> dim_movies)
  name VARCHAR(120)    -- nome de quem avaliou
  rating DOUBLE        -- nota individual dessa review
  text VARCHAR(4000)   -- texto da review
  created_at DATETIME

dim_genres: sk_genre_id PK, nome_genero VARCHAR(50)
dim_companies: sk_company_id PK, nome_produtora VARCHAR(255)
dim_people: sk_person_id PK, nome_pessoa VARCHAR(255), tipo_pessoa VARCHAR(20)
  -- tipo_pessoa tem só 3 valores possíveis: 'Ator', 'Diretor', 'Roteirista'

bridge_movie_genre (sk_movie_id, sk_genre_id) — N:N filme-gênero
bridge_movie_company (sk_movie_id, sk_company_id) — N:N filme-produtora
bridge_movie_person (sk_movie_id, sk_person_id) — N:N filme-pessoa

REGRAS DE NEGÓCIO IMPORTANTES:
- "Receita" = "Faturamento" = "Bilheteria" -> colunas receita_usd / receita_brl.
- Pergunta menciona "R$" ou "reais" -> usar SEMPRE as colunas *_brl, nunca *_usd.
- Margem de lucro = lucro / receita (calcule na própria query, não existe coluna pronta).
- "Ator" e "Diretor" são VALORES da coluna tipo_pessoa, nunca nomes de coluna ou tabela.
- Nota/avaliação de usuários agregada está em dim_reviews.nota_media_usuarios.
  Só use AVG(movie_reviews.rating) se a pergunta pedir reviews individuais/texto.
- sk_*_id são chaves hash (VARCHAR64), só servem pra JOIN — nunca filtre
  WHERE sk_movie_id = '<algo que o usuário mencionou>'.
- A query final deve ser sempre e somente SELECT (leitura).
- data_lancamento está no formato YYYY-MM-DD e contém datas futuras (até 2029). Para "últimos N anos", use BETWEEN date('now', '-N years') AND date('now')
"""
