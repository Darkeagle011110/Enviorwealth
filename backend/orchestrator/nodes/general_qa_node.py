"""
General QA Node — single-pass RAG retrieval for factual questions.

Wires the unanswerable question logger (G7 fix) so that every question
the knowledge base cannot answer is recorded in the AuditLog table.
Per §9.4: "Log every unanswerable question. That log is the product roadmap."
"""
import logging
from orchestrator.state import ConversationState
from orchestrator.llm_schemas import FactualAnswer
from orchestrator.llm_caller import llm_caller
from rag.retriever import Retriever
from utils.question_logger import log_unanswerable_question

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are answering a factual question about carbon credits.
You have been provided with context retrieved from official methodologies and regulations.
Your answer MUST be based ONLY on the provided context. Do not make up information.
If the context does not contain the answer, say so explicitly.
Always include the standard disclaimer: "This is educational information only — not legal or financial advice."
"""


async def general_qa_node(state: ConversationState) -> ConversationState:
    """
    Handles the GENERAL_QA state via single-pass RAG retrieval + generation.
    Logs unanswerable questions to the audit log (G7 fix).
    """
    state["current_node"] = "GENERAL_QA"

    if not state.get("messages"):
        return state

    user_query = state["messages"][-1]["content"]
    session_id = state.get("session_id")

    # 1. Retrieve context from knowledge base
    retriever = Retriever()
    chunks = await retriever.search(user_query, top_k=5)

    if not chunks:
        # G7 FIX: Log this unanswerable question
        await log_unanswerable_question(
            session_id=session_id,
            question=user_query,
            node="general_qa",
            reason="No matching chunks found in knowledge base",
        )
        state["messages"].append({
            "role": "assistant",
            "content": (
                "I don't have specific official guidance on that topic in my knowledge base yet. "
                "I've logged your question so we can prioritise adding that content. "
                "For now, I'd suggest checking the CCTS website (ccts.in) or Verra's project registry (registry.verra.org) directly.\n\n"
                "_This is educational information only — not legal or financial advice._"
            )
        })
        return state

    # 2. Build context block with source attribution
    context_text = "\n\n".join([
        f"[Source: {c.document_title} | Date: {c.effective_date} | Relevance: {c.score:.2f}]\n{c.text}"
        for c in chunks
    ])

    prompt = (
        f"User Question: {user_query}\n\n"
        f"Retrieved Context:\n{context_text}\n\n"
        f"Answer the question accurately, citing the source document names for any specific claims. "
        f"If the context only partially answers the question, say so."
    )

    # 3. Generate answer
    try:
        qa_output = await llm_caller.call_with_schema(
            prompt=prompt,
            schema=FactualAnswer,
            system_prompt=SYSTEM_PROMPT
        )

        state["rag_citations"] = qa_output.source_chunk_ids

        full_answer = f"{qa_output.answer}\n\n_{qa_output.disclaimer}_"
        if qa_output.last_verified_date:
            full_answer += f"\n\n*Sources last verified: {qa_output.last_verified_date}*"

        state["messages"].append({"role": "assistant", "content": full_answer})

    except Exception as e:
        logger.error(f"General QA generation failed: {e}")
        await log_unanswerable_question(
            session_id=session_id,
            question=user_query,
            node="general_qa",
            reason=f"LLM generation failed: {str(e)[:100]}",
        )
        state["messages"].append({
            "role": "assistant",
            "content": "I'm having trouble retrieving the exact answer right now. Please try again in a moment."
        })

    return state

    return state
