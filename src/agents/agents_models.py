import os
import sys
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schemas.structureds_outputs import IsQueryQuestion, SQLquery, SQLvalidationResult, QueryExecutionResult, AnswerSumary
from agents.schema_context import DB_SCHEMA_DESCRIPTION 



load_dotenv()

gpt_os = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=(os.getenv("GROQ_API_KEY")),
    temperature= 0.0,
)

groq_comp = ChatGroq(
    model="groq/compound",
    api_key=(os.getenv("GROQ_API_KEY")),
    temperature= 0.0
)



def agent_verify_if_is_a_query_Question(input: str) -> IsQueryQuestion:
    agent_verifier = gpt_os.with_structured_output(schema=IsQueryQuestion)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", 
             "You are a query verifier. You will receive a question and you must determine if the question is asking for a SQL query about the CineData database. "
             "If it is, return True. If it is not, return False."),
            ("human", "{question}"),
        ]
    )
    chain_agent_verifier = prompt | agent_verifier
    result = chain_agent_verifier.invoke({"question": input})

    return result

def agent_generator_sql(question: str, feedback: Optional[str] = None) ->SQLquery:
    agent_generator = gpt_os.with_structured_output(schema=SQLquery)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", 
             "You are a SQL query generator. You will receive a question and you must generate a SQL SELECT query that answers the question, based on the database schema provided below. "
             "The database is read-only and you must not generate any queries that modify the database (no INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, ATTACH, DETACH, PRAGMA, REPLACE, VACUUM or REINDEX). "
             "You must also provide an explanation of how the query was constructed.\n\n" + DB_SCHEMA_DESCRIPTION),
            ("human", "{input}"),
        ]
    )
    chain_agent_generator = prompt | agent_generator
    full_question = question
    if feedback:
        full_question = f'{question} \n\n[CORREÇÃO NECESSÁRIA NA TENTATIVA ANTERIOR: {feedback}]'
    result = chain_agent_generator.invoke({"input": full_question})

    return result

def agent_validator_sql(sql_query: SQLquery) -> SQLvalidationResult:
    agent_validator = gpt_os.with_structured_output(schema=SQLvalidationResult)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", 
             "You are a SQL query validator. You will receive a SQL SELECT query in the user message."
             " You  must validate if the query is safe and coherent with the database schema provided below. "
             "The database is read-only and you must not approve any queries that modify the database (no INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, ATTACH, DETACH, PRAGMA, REPLACE, VACUUM or REINDEX). "
             "You must also provide a reason for disapproval if the query is not approved.\n\n" + DB_SCHEMA_DESCRIPTION),
            ("human", 
             "Original question/objective: {objective}\n"
             "Explanation about the query: {explanation}\n"
             "Query generated: {sql}\n")
        ]
    )
    chain_agent_validator = prompt | agent_validator
    result = chain_agent_validator.invoke({"objective": sql_query.objective,"explanation": sql_query.explanation,"sql": sql_query.sql})

    return result

def agent_synthesizer_answer(sql_query: SQLquery, query_result: QueryExecutionResult) -> AnswerSumary:
    agent_synthesizer = gpt_os.with_structured_output(schema=AnswerSumary)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", 
             "You are an agent who will provide a general summary of the results of the requirements, "
            "and the final query results."),
            ("human", 
             "Original Question: {objective}\n"
             "Returned Columns: {columns}\n"
             "Returned Rows: {rows}\n"
             "You must provide a summary of the results, in Portuguese, that is direct and cites the numbers found."),
        ]
    )
    chain_agent_synthesizer = prompt | agent_synthesizer
    result = chain_agent_synthesizer.invoke({"objective": sql_query.objective,"columns": query_result.columns,"rows": query_result.rows,"row_count": query_result.row_count})

    return result
















