"""Interface Streamlit para consultas analíticas no CineData."""

from __future__ import annotations

import sys
from pathlib import Path
import uuid
import pandas as pd
import streamlit as st



PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
    
from services.memory_store import clear_session
from graph.agents_graphs import PipelineState, run_cinedata_pipeline


st.set_page_config(page_title="CineData Analytics", page_icon="🎬", layout="wide")

EXAMPLES = [
    "Quais são os 10 filmes com maior receita em R$?",
    "Qual a nota média por gênero?",
    "Quantos filmes foram lançados por ano?",
]


def _set_question(text: str) -> None:
    st.session_state["question"] = text


def _get_frame(state: PipelineState) -> pd.DataFrame | None:
    execution = state.get("execution")
    if execution is None or not execution.rows:
        return None
    return pd.DataFrame(execution.rows, columns=execution.columns)


# ---------- blocos de UI ----------

def _render_summary(state: PipelineState) -> None:
    answer = state.get("answer")
    frame = _get_frame(state)
    generated_sql = state.get("generated_sql")

    if state.get("is_on_topic") is False:
        st.warning(state.get("off_topic_reason") or "Pergunta fora do escopo do CineData.")
        return

    with st.container(border=True):
        st.markdown("### 💬 Resposta")
        if answer:
            text = _safe_markdown(answer.answer)
            if state.get("success"):
                st.success(text)     
            else:
                st.warning(text)
        else:
            st.error(state.get("last_error") or "Não foi possível gerar uma resposta.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Status", "Sucesso ✅" if state.get("success") else "Com ressalvas ⚠️")
    c2.metric("Tentativas", f"{state.get('attempt', 0)}/{state.get('max_attempts', 3)}")
    c3.metric("Linhas retornadas", len(frame) if frame is not None else 0)
    c4.metric("Categoria", generated_sql.category.value if generated_sql else "—")


def _render_data_tab(state: PipelineState) -> None:
    frame = _get_frame(state)
    if frame is None:
        st.info("A consulta não retornou dados.")
        return

    st.dataframe(frame, width="stretch", hide_index=True)
    st.download_button(
        "⬇️ Baixar CSV",
        frame.to_csv(index=False).encode("utf-8"),
        file_name="cinedata_resultado.csv",
        mime="text/csv",
        width="stretch",
    )

    numeric_cols = list(frame.select_dtypes(include="number").columns)
    if not numeric_cols:
        return

    st.markdown("#### 📊 Gráfico")
    label_cols = [c for c in frame.columns if c not in numeric_cols] or [None]
    col1, col2, col3 = st.columns(3)
    label = col1.selectbox("Eixo X (rótulo)", label_cols, format_func=lambda c: c or "(índice)")
    metric = col2.selectbox("Métrica", numeric_cols)
    kind = col3.radio("Tipo", ["Barras", "Linha"], horizontal=True)

    chart = frame.set_index(label)[[metric]] if label else frame[[metric]]
    (st.bar_chart if kind == "Barras" else st.line_chart)(chart.dropna())

    st.title(' Por de Baixo dos Panos', icon='🔍')
    with st.expander("Respostas dos Agentes"):
        st.subheader("Agente Verificador")
        st.write(state.get("answer_agent_verifier", "—"))
        st.subheader("Agent Gerador SQL")
        st.write(state.get("answer_agent_generator", "—"))
        st.subheader("Agent Validador")
        st.write(state.get("answer_agent_validator", "—"))
        st.subheader("Agent Executor")
        st.write(state.get("answer_agent_executor", "—"))
        st.subheader("Agent Sintetizador")
        st.write(state.get("answer_agent_synthesizer", "—"))

def _render_sql_tab(state: PipelineState) -> None:
    generated_sql = state.get("generated_sql")
    validation = state.get("validation")
    if generated_sql:
        st.markdown("**Explicação da consulta**")
        st.write(generated_sql.explanation)
        st.code(generated_sql.sql, language="sql")
    if validation:
        if validation.approved:
            st.success("Validação aprovada")
        else:
            st.error("Validação reprovada")
        if validation.reason:
            st.caption(validation.reason)


def _render_agents_tab(state: PipelineState) -> None:
    validation = state.get("validation")
    decisions = state.get("decision_order", [])
    executor_ran = any(d.startswith("Executor") for d in decisions)
    executor_ok = state.get("execution") is not None

    steps = [
        ("Verificador", state.get("is_on_topic")),
        ("Gerador SQL", state.get("generated_sql") is not None or None),
        ("Validador", validation.approved if validation else None),
        ("Executor", True if executor_ok else (False if executor_ran else None)),
        ("Sintetizador", True if state.get("answer_agent_synthesizer") else None),
    ]
    icons = {True: "✅", False: "❌", None: "⏭️"}

    for col, (name, ok) in zip(st.columns(len(steps)), steps):
        with col, st.container(border=True):
            st.markdown(f"## {icons[ok]}")
            st.caption(name)

    decisions = state.get("decision_order", [])
    if decisions:
        st.markdown("#### Ordem das decisões")
        for i, decision in enumerate(decisions, start=1):
            st.markdown(f"**{i}.** {decision}")

    if state.get("last_error"):
        st.warning(state["last_error"])


def _render_result(state: PipelineState) -> None:
    _render_summary(state)
    if state.get("is_on_topic") is False:
        return
    tab_data, tab_sql, tab_agents = st.tabs(["📋 Dados e gráfico", "🧾 SQL", "🤖 Agentes"])
    with tab_data:
        _render_data_tab(state)
    with tab_sql:
        _render_sql_tab(state)
    with tab_agents:
        _render_agents_tab(state)

def _safe_markdown(text: str) -> str:
    """Escapa '$' pra o Streamlit não interpretar 'R$ ... R$' como fórmula LaTeX."""
    return text.replace("$", r"\$")
# ---------- app ----------

def main() -> None:
    st.session_state.setdefault("session_id", uuid.uuid4().hex)
    st.session_state.setdefault("history", [])
    st.title("🎬 CineData Analytics")
    st.caption("Pergunte em linguagem natural.")
    with st.expander('Aviso', expanded=False):
        st.info(
            "Os modelos GRÁTIS do Groq permitem apenas 8000 tokens por minuto, então é recomendado que você dê um tempinho entre as perguntasd de no máximo 1 minuto. Para que os tokens resetem e não estoure erro de limite de requisições."
        )
    with st.sidebar:
        st.header("💡 Exemplos")
        for example in EXAMPLES:
            st.button(example, on_click=_set_question, args=(example,), width="stretch")
        st.divider()
        if st.button("🗑️ Limpar conversa", width="stretch"):
            clear_session(st.session_state["session_id"])
            st.session_state["history"] = []
            st.session_state["session_id"] = uuid.uuid4().hex
            st.session_state.pop("state", None)
            st.rerun()

    question = st.text_area(
        "Sua pergunta",
        key="question",
        placeholder="Ex.: Quais são os 10 filmes com maior receita em R$?",
        height=90,
    )

    if st.button("Analisar", type="primary", width="stretch"):
        if not question.strip():
            st.error("Digite uma pergunta para iniciar a análise.")
        else:
            try:
                with st.spinner("Os agentes estão analisando sua pergunta..."):
                    state = run_cinedata_pipeline(
                        question.strip(),
                        max_attempts=3,
                        session_id=st.session_state["session_id"],
                        history=st.session_state["history"],
                    )
                st.session_state["state"] = state
                if state.get("success"):
                    st.session_state["history"].append({
                        "question": state.get("standalone_question", question.strip()),
                        "answer": state["answer"].answer,
                    })
            except Exception as exc:
                st.session_state.pop("state", None)
                st.error(f"Algo deu errado ao rodar o pipeline: {exc}")

    if "state" in st.session_state:
        st.divider()
        _render_result(st.session_state["state"])


if __name__ == "__main__":
    main()