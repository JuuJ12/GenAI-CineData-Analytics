"""Memória de longo prazo da conversa (Chroma), isolada por sessão do usuário."""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHROMA_MEMORY_PATH = PROJECT_ROOT / "chroma_memory"  # colocar no .gitignore
COLLECTION_NAME = "memoria_conversa"
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

_collection = None


def _get_collection():
    """Cria a coleção uma vez só (carregar o modelo de embedding é a parte lenta)."""
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=str(CHROMA_MEMORY_PATH))
        embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )
        _collection = client.get_or_create_collection(
            COLLECTION_NAME,
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def add_turn(session_id: str, question: str, sql: str | None, answer: str) -> None:
    """Salva uma interação concluída com sucesso."""
    _get_collection().add(
        ids=[uuid.uuid4().hex],
        documents=[f"Pergunta: {question}\nResposta: {answer}"],
        metadatas=[{
            "session_id": session_id,
            "question": question,
            "sql": sql or "",
            "answer": answer[:500],
            "ts": time.time(),
        }],
    )


def recall(session_id: str, query: str, k: int = 3) -> list[dict]:
    """Interações antigas desta sessão mais parecidas com a pergunta atual."""
    collection = _get_collection()
    total = collection.count()
    if total == 0:
        return []
    result = collection.query(
        query_texts=[query],
        n_results=min(k, total),
        where={"session_id": session_id},
    )
    return [
        {"question": m["question"], "answer": m["answer"], "sql": m["sql"]}
        for m in result["metadatas"][0]
    ]


def clear_session(session_id: str) -> None:
    """Apaga a memória desta sessão (botão 'Limpar conversa')."""
    _get_collection().delete(where={"session_id": session_id})