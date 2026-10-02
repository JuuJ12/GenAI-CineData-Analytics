import os
import operator
import sys
import sys
from pathlib import Path
from typing import Annotated, Optional, TypedDict
from langgraph.graph import StateGraph, START, END

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.agents_models import (agent_generator_sql, agent_validator_sql, 
                                  agent_synthesizer_answer, agent_verify_if_is_a_query_Question)
from schemas.structureds_outputs import QueryExecutionResult, SQLquery, SQLvalidationResult,  AnswerSumary
from services.sql_executor import execute_read_only_query, SQLSecurityError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = os.getenv(
    "DB_PATH",
    str(PROJECT_ROOT / "data" / "cinerocket.db"),
)

class PipelineState(TypedDict, total = False):
    """Define o estado do pipeline de execução de SQL"""
    question: str
    max_attempts: int
    attempt: int

    is_on_topic: bool
    off_topic_reason: Optional[str]

    generated_sql: Optional[SQLquery]
    validation: Optional[SQLvalidationResult]
    execution: Optional[QueryExecutionResult]
    answer: Optional[AnswerSumary]

    last_error: Optional[str]
    success: bool
    decision_order: Annotated[list[str], operator.add]




def node_verify(state: PipelineState) -> PipelineState: #node condicional
    result = agent_verify_if_is_a_query_Question(state["question"])
    return {'is_on_topic': result.is_answer,
            'off_topic_reason': result.reason,
            'attempt':0,
            'max_attempts': state.get('max_attempts', 3),
            'decision_order': [
                f"Verificador: {'aceitou' if result.is_answer else 'rejeitou'} a pergunta"
            ]}

def node_reject(state: PipelineState) -> dict:
    reason = state.get('off_topic_reason', 'Pergunta não é sobre SQL ou sobre o banco de dados CineData')
    return{
        'answer': AnswerSumary(answer=f"Não consigo responder isso com os dados do CineData:{reason}"),
        'success': False,
        'decision_order': ["Roteador: enviou a pergunta para rejeição"],
    }


def node_generate_sql(state: PipelineState) -> PipelineState:
    attempt = state.get('attempt', 0) + 1
    generated_sql = agent_generator_sql(state["question"], feedback=state.get('last_error'))

    return {'generated_sql': generated_sql,
            'attempt': attempt,
            'decision_order': [
                f"Gerador SQL: criou a consulta (tentativa {attempt})"
            ]}

def node_validate_sql(state: PipelineState) -> PipelineState: #node condicional
    validation = agent_validator_sql(state["generated_sql"])
    if not validation.approved:
        return {'validation': validation,
                'last_error': validation.reason,
                'decision_order': [
                    "Validador: reprovou a consulta e solicitou nova tentativa"
                ]}
    return {'validation': validation,
            'last_error': None,
            'decision_order': ["Validador: aprovou a consulta"]}

def node_execute_sql(state: PipelineState) -> dict:
    try:
        result = execute_read_only_query(state["generated_sql"].sql, db_path =DB_PATH)
        return {
            'execution': result,
            'last_error': None,
            'decision_order': [
                "Executor: executou a consulta em modo somente leitura"
            ],
        }
    except SQLSecurityError as exc:
        return {
            'last_error': f'Erro na execução da query: {exc}',
            'decision_order': [
                "Executor: bloqueou a consulta e solicitou nova tentativa"
            ],
        }

def node_synthesize_answer(state: PipelineState) -> PipelineState:
    answer = agent_synthesizer_answer(state["generated_sql"], state["execution"], state["decision_order"]   )
    return {
        'answer': answer,
        'success': True,
        'decision_order': ["Sintetizador: formulou a resposta final"],
    }

def node_fail(state: PipelineState) -> dict:
    return {'answer': AnswerSumary(
        answer=(
            f"Não consegui gerar uma consulta válida após {state.get('max_attempts')} "
            f"tentativas. Último problema: {state.get('last_error')}"
        )
    ), 'success': False,
        'decision_order': [
            "Pipeline: encerrou após atingir o limite de tentativas"
        ],
    }



def route_after_verify(state: PipelineState) -> str:
    return 'generate' if state.get('is_on_topic') else 'reject'

def _retry_fail_or_continue(state: PipelineState, happy_path:str) -> str:
    if state.get('last_error'):
        if state['attempt'] >= state['max_attempts']:
            return 'fail'
        return 'retry'
    return happy_path

def route_after_validate(state: PipelineState) -> str:
    return _retry_fail_or_continue(state, happy_path='execute')

def route_after_execute(state: PipelineState) -> str:
    return _retry_fail_or_continue(state, happy_path='synthesize')


builder = StateGraph(PipelineState)
builder.add_node('verify', node_verify)
builder.add_node('reject', node_reject)
builder.add_node("generate_sql", node_generate_sql)
builder.add_node("validate_sql", node_validate_sql)
builder.add_node("execute", node_execute_sql)
builder.add_node("synthesize_answer", node_synthesize_answer)
builder.add_node('fail', node_fail)

builder.add_edge(START, "verify")
builder.add_conditional_edges("verify", route_after_verify, {"generate": "generate_sql", "reject": "reject"})

builder.add_edge("generate_sql", "validate_sql")
builder.add_conditional_edges("validate_sql", route_after_validate, {"execute": "execute", "retry": "generate_sql", "fail": "fail"})

builder.add_conditional_edges("execute", route_after_execute, {"synthesize": "synthesize_answer", "retry": "generate_sql", "fail": "fail"})

builder.add_edge("reject", END)
builder.add_edge("fail", END)
builder.add_edge("synthesize_answer", END)

cinedata_graph = builder.compile()

#cinedata_graph.get_graph().draw_mermaid_png(output_file_path="cinedata_graph.png")

def run_cinedata_pipeline(question: str, max_attempts: int = 3) -> PipelineState:
    return cinedata_graph.invoke({'question': question, 'max_attempts': max_attempts})

# print(run_cinedata_pipeline("Qual é o ator com mais participações em filmes lançados nos últimos 5 anos?").get('generated_sql').sql)
# print(run_cinedata_pipeline(" Ator com mais participações em filmes lançados nos últimos 5 anos"))

print(agent_generator_sql("Ator com mais participações em filmes lançados nos últimos 5 anos").sql)