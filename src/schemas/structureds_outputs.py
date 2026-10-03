from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field

class QuestionCategory(str, Enum):
    BILHETERIA_FINACAS = 'bilheteria_financas'
    POPULARIDADE_ENGAJAMENTO = 'popularidade_engajamento'
    ELENCO_EQUIPE = 'elenco_equipe'
    GENERO_PRODUTORAS = 'genero_produtoras'
    AVALIACOES_USUARIOS = 'avaliacoes_usuarios'
    OUTRA = 'outra'

class SQLquery(BaseModel):
    """Isso aqui é o modelo de resposta que o nosso agente GERADOR de SQL vai retornar"""
    objective: str = Field(..., description="Objetivo da query, que é a pergunta do usuário")
    sql: str = Field(..., description="A query SQL SELECT completa, pronta pra executar no SQLite")
    category: QuestionCategory = Field(..., description="Categoria da pergunta do usuário")
    explanation: str = Field(..., description="Explicação detalhada de como a query foi construída, incluindo quais tabelas foram usadas e como as colunas foram selecionadas")

class SQLvalidationResult(BaseModel):
    """Isso aqui é o modelo de resposta que o nosso agente VALIDADOR de SQL vai retornar"""
    approved: bool = Field(..., description="True se a query é segura e coerente com o schema do banco de dados, False caso contrário")
    reason: Optional[str] = Field(None, description="Motivo da reprovação, se approved=False (ex: usa coluna inexistente, "
        "não é somente leitura, não responde à pergunta original)")

class QueryExecutionResult(BaseModel):
    """"Resultado da execução real no SQLite, não vai vim de LLM, vai ser montado em pyhton"""
    columns: List[str] = Field(..., description="Lista de nomes das colunas retornadas pela query")
    rows: List[List] = Field(..., description="Lista de linhas retornadas pela query, cada linha é uma lista de valores")
    row_count: int = Field(..., description="Número de linhas retornadas pela query")

class AnswerSumary(BaseModel):
    """Resumo da resposta que o agente sintetizador vai retornar pro usuário"""
    answer: str = Field(..., description="Resposta em português, direta, citando os números encontrados")

class IsQueryQuestion(BaseModel):
    """Modelo de resposta do agente que valida se o usário esta pedindo uma consulta SQL sobre o CineData"""
    is_answer: bool = Field(..., description="True se o usuário está pedindo uma consulta SQL sobre o CinetaData, False caso contrário")
    reason: Optional[str] = Field(None, description="Motivo da reprovação")

class RewrittenQuestion(BaseModel):
    question: str = Field(description="Pergunta completa e independente, em português")