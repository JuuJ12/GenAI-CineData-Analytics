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
- "Ator" e "Diretor" são VALORES da coluna tipo_pessoa, nunca nomes de coluna ou tabela.
- Nota/avaliação de usuários agregada está em dim_reviews.nota_media_usuarios.
  Só use AVG(movie_reviews.rating) se a pergunta pedir reviews individuais/texto.
- sk_*_id são chaves hash (VARCHAR64), só servem pra JOIN — nunca filtre
  WHERE sk_movie_id = '<algo que o usuário mencionou>'.
- A query final deve ser sempre e somente SELECT (leitura).
- Respeite a quantidade pedida: "o gênero / o ator / a dupla" -> LIMIT 1; "top N" -> LIMIT N.
- data_lancamento está no formato YYYY-MM-DD e contém datas futuras (até 2029).
  Para "últimos N anos", use BETWEEN date('now', '-N years') AND date('now').

REGRAS FINANCEIRAS (dados têm lixo: valor 0 = não informado; receitas minúsculas, ex. US$ 12,
geram margens absurdas):
- Margem de lucro = lucro / receita (calcule na própria query; é uma razão, vale em USD ou BRL).
- Para perguntas de MARGEM: sempre filtre receita_usd >= 10000 AND orcamento_usd > 0.
- Para "lucro médio" com "receita informada": filtre apenas receita > 0.
- Ao agrupar por gênero/produtora em perguntas de margem: HAVING COUNT(*) >= 10
  e mostre sempre COUNT(*) AS filmes.

Exemplo (margem por gênero) — siga este padrão:
SELECT g.nome_genero,
       ROUND(AVG(f.lucro_usd * 1.0 / f.receita_usd), 4) AS margem_media,
       COUNT(*) AS filmes
FROM fact_movies_performance f
JOIN bridge_movie_genre bg ON bg.sk_movie_id = f.sk_movie_id
JOIN dim_genres g ON g.sk_genre_id = bg.sk_genre_id
WHERE f.receita_usd >= 10000 AND f.orcamento_usd > 0
GROUP BY g.sk_genre_id, g.nome_genero
HAVING COUNT(*) >= 10
ORDER BY margem_media DESC
LIMIT 1

REGRA CRÍTICA DE DESEMPENHO (bridge_movie_person):
A tabela bridge_movie_person é muito grande. NUNCA faça JOIN dela com ela mesma sem filtrar
o tipo da pessoa antes (produto cartesiano -> timeout). Para cruzar dois papéis no mesmo filme
(ex.: ator e diretor), use CTEs filtrando cada papel separadamente ANTES do JOIN.
Nunca agrupe por nome (texto): agrupe por ID e busque o nome só no final.

Exemplo (dupla ator-diretor) — siga este padrão:
WITH atores AS (
  SELECT b.sk_movie_id, b.sk_person_id
  FROM bridge_movie_person b JOIN dim_people p ON p.sk_person_id = b.sk_person_id
  WHERE p.tipo_pessoa = 'Ator'
),
diretores AS (
  SELECT b.sk_movie_id, b.sk_person_id
  FROM bridge_movie_person b JOIN dim_people p ON p.sk_person_id = b.sk_person_id
  WHERE p.tipo_pessoa = 'Diretor'
),
top AS (
  SELECT a.sk_person_id AS ator_id, d.sk_person_id AS diretor_id,
         COUNT(DISTINCT a.sk_movie_id) AS filmes
  FROM atores a JOIN diretores d ON d.sk_movie_id = a.sk_movie_id
  WHERE a.sk_person_id <> d.sk_person_id
  GROUP BY a.sk_person_id, d.sk_person_id
  ORDER BY filmes DESC LIMIT 1
)
SELECT pa.nome_pessoa AS ator, pd.nome_pessoa AS diretor, top.filmes
FROM top JOIN dim_people pa ON pa.sk_person_id = top.ator_id
         JOIN dim_people pd ON pd.sk_person_id = top.diretor_id
"""