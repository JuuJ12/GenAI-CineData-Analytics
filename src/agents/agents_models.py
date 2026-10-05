import os
import sys
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import PydanticOutputParser

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schemas.structureds_outputs import IsQueryQuestion, SQLquery, SQLvalidationResult, QueryExecutionResult, AnswerSumary, RewrittenQuestion
from agents.schema_context import DB_SCHEMA_DESCRIPTION 



load_dotenv()

gemini = ChatGoogleGenerativeAI(
    model="gemini-3.8-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.0,
    max_output_tokens=4096,
    max_retries = 0
)

gpt_os = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=(os.getenv("GROQ_API_KEY")),
    temperature= 0.0,
    max_tokens=4096,
    max_retries=0,
    reasoning_effort = 'low'
)

gpt_os2= ChatGroq(
    model="openai/gpt-oss-20b",
    api_key=(os.getenv("GROQ_API_KEY")),
    temperature= 0.0,
    max_tokens=4096
)


def agent_verify_if_is_a_query_Question(input: str) -> IsQueryQuestion:
    parser = PydanticOutputParser(pydantic_object=IsQueryQuestion)
    
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system",
            "You are a gatekeeper for a movie analytics assistant (CineData).\n"
            "Decide if the question can be answered with data from the CineData database. "
            "Users write in natural language and do NOT need to mention SQL.\n"
            "The database covers: movies (title, release date, runtime, status), financials "
            "(budget, revenue, profit), popularity and ratings (TMDB, IMDb, user ratings and reviews), "
            "genres, production companies, and people (actors, directors, writers) linked to movies.\n"
            "Return is_answer=true for any question about these topics, including rankings, averages, "
            "counts and pairs (e.g. which actor-director pair worked together the most).\n"
            "Return is_answer=false only for unrelated questions (weather, general knowledge, coding help) "
            "or requests to modify data.\n"
            "If in doubt and the question is about movies, return true.\n"
            "You must respond in Portuguese, including the reason field.\n\n"
            "You MUST strictly follow this exact JSON format:\n{format_instructions}"),
            ("human", "{question}"),
        ]
    )
    chain_agent_verifier = prompt | gpt_os2 | parser
    
    result = chain_agent_verifier.invoke({
        "question": input,
        "format_instructions": parser.get_format_instructions()
    })
    return result

def agent_rewrite_question(question: str, recent: list[dict], recalled: list[dict]) -> RewrittenQuestion:
    parser = PydanticOutputParser(pydantic_object=RewrittenQuestion)
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "Rewrite the current question as a complete, standalone question.\n"
        "Use the history ONLY to resolve references like 'of these', 'and the second one?', "
        "'in the last 3 years?'. If the question is already standalone, return it as is.\n"
        "Do not answer the question and do not invent filters the user did not ask for.\n"
        "Respond in Portuguese.\n\n"
         "You MUST strictly follow this exact JSON format:\n{format_instructions}"),
        ("human",
         "Histórico recente:\n{recent}\n\nInterações antigas relacionadas:\n{recalled}\n\n"
         "Pergunta atual: {question}"),
    ])
    fmt = lambda turns: "\n".join(f"- P: {t['question']} | R: {t['answer']}" for t in turns) or "(nenhum)"
    return (prompt | gpt_os2 | parser).invoke({
        "question": question, "recent": fmt(recent), "recalled": fmt(recalled),
        "format_instructions": parser.get_format_instructions(),
    })

def agent_generator_sql(question: str, feedback: Optional[str] = None) -> SQLquery:
    parser = PydanticOutputParser(pydantic_object=SQLquery)
    
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", 
             "You are a SQL query generator. Generate a SQL SELECT query based on the schema.\n"
             "The database is read-only. Do not generate modifying queries.\n"
             "You must respond entirely in Portuguese.\n\n"
             "CRITICAL RULES:\n"
             "1. Keep 'explanation' extremely short.\n"
             "2. The 'sql' field MUST be written in a single continuous line. DO NOT use line breaks (\\n).\n\n"
             "You MUST strictly follow this exact JSON format:\n{format_instructions}\n\n"
             "Database Schema:\n{schema}"),
            ("human", "{input}"),
        ]
    )
    
    chain_agent_generator = prompt | gpt_os | parser
    
    full_question = question
    if feedback:
        full_question = f'{question} \n\n[CORREÇÃO NECESSÁRIA: {feedback}]'
        
    result = chain_agent_generator.invoke({
        "input": full_question,
        "format_instructions": parser.get_format_instructions(),
        "schema": DB_SCHEMA_DESCRIPTION
    })
    return result


def agent_validator_sql(sql_query: SQLquery) -> SQLvalidationResult:
    parser = PydanticOutputParser(pydantic_object=SQLvalidationResult)
    
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", 
             "You are a SQL query validator. Validate if the query is safe and coherent.\n"
             "The database is read-only. Reject modifying queries.\n"
             "You must respond entirely in Portuguese.\n\n"
             "You MUST strictly follow this exact JSON format:\n{format_instructions}\n\n"
             "Database Schema:\n{schema}"),
            ("human", 
             "Original question/objective: {objective}\n"
             "Explanation about the query: {explanation}\n"
             "Query generated: {sql}")
        ]
    )
    
    chain_agent_validator = prompt | gpt_os | parser
    
    result = chain_agent_validator.invoke({
        "objective": sql_query.objective,
        "explanation": sql_query.explanation,
        "sql": sql_query.sql,
        "format_instructions": parser.get_format_instructions(),
        "schema": DB_SCHEMA_DESCRIPTION
    })
    return result


def agent_synthesizer_answer(sql_query: SQLquery, query_result: QueryExecutionResult, decision_order: list[str]) -> AnswerSumary:
    parser = PydanticOutputParser(pydantic_object=AnswerSumary)
    
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", 
             "You are an agent who provides a summary of the query results.\n"
             "You must respond entirely in Portuguese.\n\n"
             "CRITICAL RULES:\n"
             "1. The 'answer' field MUST be a single continuous string.\n"
             "2. Keep the summary concise (max 3 sentences). DO NOT list every single row.\n\n"
             "You MUST strictly follow this exact JSON format:\n{format_instructions}"),
            ("human", 
             "Decision Order: {decision_order}\n"
             "Original Question: {objective}\n"
             "Returned Columns: {columns}\n"
             "Returned Rows: {rows}\n"
             "Provide the final summary.")
        ]
    )
    
    chain_agent_synthesizer = prompt | gpt_os2 | parser
    
    result = chain_agent_synthesizer.invoke({
        "objective": sql_query.objective,
        "columns": query_result.columns,
        "rows": query_result.rows[:20],
        "decision_order": decision_order[-8:],
        "format_instructions": parser.get_format_instructions()
    })
    return result











