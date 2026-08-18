"""
rag_agent.py — The primary knowledge agent.

Consolidates:
  - general_qa_node   (single-pass RAG for factual questions)
  - agentic_loop_node (iterative retrieval for complex questions)
  - consult_node      (casual domain chat)
  - offer_review_node (contract analysis)

Routing within this agent:
  1. Retrieve from Qdrant knowledge base (top-k = 5)
  2. If results are good → generate answer using RAG context
  3. If results are insufficient → agentic critic loop (max 3 iterations)
  4. If still insufficient → set state["rag_sufficient"] = False so the
     orchestrator cascades to the Web Search Agent

All answers include conversation context (summary + last 5 messages)
for coherent multi-turn replies.
"""
import logging
from typing import List
from pydantic import BaseModel, Field
from typing import Optional

from orchestrator.state import ConversationState
from orchestrator.llm_caller import llm_caller
from orchestrator.agents.context_manager import build_context_block
from rag.retriever import Retriever, Chunk
from utils.question_logger import log_unanswerable_question

logger = logging.getLogger(__name__)

MAX_AGENTIC_ITERATIONS = 3
MIN_RETRIEVAL_SCORE = 0.30   # cosine score below this = no useful results


# ─── Pydantic schemas ─────────────────────────────────────────────────────────

class RAGAnswer(BaseModel):
    answer: str = Field(..., description="The factual answer, referencing source document names where relevant.")
    source_chunk_ids: List[str] = Field(default_factory=list)
    last_verified_date: Optional[str] = Field(None)
    disclaimer: str = Field(..., description="Standard disclaimer — educational info, not legal/financial advice.")


class CriticOutput(BaseModel):
    is_sufficient: bool = Field(..., description="True if context fully answers the question.")
    missing_info: Optional[str] = Field(None, description="What is still missing?")
    refined_query: Optional[str] = Field(None, description="A better search query to find missing info.")


class OfferReviewOutput(BaseModel):
    analysis: str = Field(..., description="Plain-English analysis of the contract terms.")
    red_flags: List[str] = Field(default_factory=list, description="Predatory or concerning terms.")
    follow_up_question: Optional[str] = Field(None, description="Question to clarify offer terms.")


# ─── System prompts ───────────────────────────────────────────────────────────

RAG_ANSWER_SYSTEM = """You are a knowledgeable carbon credit consultant for EnviroWealth.
Answer the user's question using ONLY the provided context from the knowledge base.
You have access to the conversation history — use it to give contextually relevant answers.
If the context only partially answers the question, say so honestly.
Do NOT invent facts. Do NOT cite methodology versions from memory (use only what is in the context).
Always end with the disclaimer: "This is educational information only — not legal or financial advice."
"""

CRITIC_SYSTEM = """You are evaluating whether retrieved context is sufficient to answer a complex question.
Output is_sufficient=True only if the context FULLY answers the question.
If not, specify exactly what is missing and provide a refined, more specific search query.
"""

OFFER_REVIEW_SYSTEM = """You are a consumer protection assistant helping carbon credit landowners review contracts.
The user is sharing terms from a developer's offer. Analyse it objectively.
Flag any of: who owns carbon rights, what happens on tree failure/reversal, the revenue split,
hidden fees, exit penalties, or unusually long lock-in periods.
Always state: "This analysis is based on standard carbon market practices — not professional legal advice."
"""

GENERAL_CHAT_SYSTEM = """You are EnviroWealth's carbon credit consultant.
You have no specific knowledge base context for this question, but you can still have a helpful,
grounded conversation about carbon credits, climate, and land use in India.
Do not invent specific numbers, methodology versions, or regulatory details.
If you're uncertain, say so and suggest checking primary sources.
"""


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _format_chunks(chunks: List[Chunk]) -> str:
    return "\n\n".join(
        f"[Source: {c.document_title} | Date: {c.effective_date} | Score: {c.score:.2f}]\n{c.text}"
        for c in chunks
    )


def _chunks_are_useful(chunks: List[Chunk]) -> bool:
    if not chunks:
        return False
    return any(c.score and c.score >= MIN_RETRIEVAL_SCORE for c in chunks)


# ─── Sub-handlers ─────────────────────────────────────────────────────────────

async def _handle_offer_review(
    state: ConversationState,
    user_query: str,
    context_block: str,
) -> ConversationState:
    """Handle contract/offer review requests."""
    prompt = (
        f"{context_block}\n\n"
        f"User's contract or offer question:\n{user_query}"
    )
    try:
        output = await llm_caller.call_with_schema(
            prompt=prompt,
            schema=OfferReviewOutput,
            system_prompt=OFFER_REVIEW_SYSTEM,
        )
        reply = output.analysis
        if output.red_flags:
            flags = "\n".join(f"⚠️ {f}" for f in output.red_flags)
            reply += f"\n\n**Things to watch out for:**\n{flags}"
        if output.follow_up_question:
            reply += f"\n\n{output.follow_up_question}"
        reply += "\n\n_This analysis is based on standard carbon market practices — not professional legal advice. Always consult a lawyer before signing._"
        state["messages"].append({"role": "assistant", "content": reply})
    except Exception as e:
        logger.error(f"Offer review failed: {e}")
        state["messages"].append({
            "role": "assistant",
            "content": "I couldn't analyse the offer right now. Please seek independent legal advice before signing any contract.",
        })
    return state


async def _retrieve_with_agentic_loop(
    original_query: str,
) -> List[Chunk]:
    """
    Agentic retrieval: try initial query, then use a critic to refine
    the query if the first results are insufficient.
    Returns the best accumulated chunks found.
    """
    retriever = Retriever()
    current_query = original_query
    accumulated: List[Chunk] = []
    seen_ids: set = set()

    for iteration in range(MAX_AGENTIC_ITERATIONS):
        logger.info(f"RAG retrieval iteration {iteration + 1}: '{current_query[:80]}'")
        chunks = await retriever.search(current_query, top_k=5)

        # Add new unique chunks
        for c in chunks:
            if c.chunk_id not in seen_ids:
                seen_ids.add(c.chunk_id)
                accumulated.append(c)

        # If we have good results, stop early
        if _chunks_are_useful(accumulated) and iteration >= 1:
            break

        if iteration < MAX_AGENTIC_ITERATIONS - 1:
            # Critic step — should we refine?
            context_text = _format_chunks(accumulated) if accumulated else "(no results)"
            critic_prompt = (
                f"Original question: {original_query}\n\n"
                f"Accumulated context:\n{context_text}\n\n"
                "Is this context sufficient to fully answer the question?"
            )
            try:
                critic = await llm_caller.call_with_schema(
                    prompt=critic_prompt,
                    schema=CriticOutput,
                    system_prompt=CRITIC_SYSTEM,
                )
                if critic.is_sufficient:
                    logger.info("Critic: context sufficient. Stopping retrieval.")
                    break
                elif critic.refined_query:
                    current_query = critic.refined_query
                    logger.info(f"Critic: refining query to '{current_query[:80]}'")
                else:
                    break
            except Exception as e:
                logger.warning(f"Critic step failed: {e}. Stopping retrieval.")
                break

    return accumulated


# ─── Main RAG agent ───────────────────────────────────────────────────────────

async def rag_agent(state: ConversationState) -> ConversationState:
    """
    Handles all domain Q&A via RAG retrieval + agentic refinement.
    Sets state["rag_sufficient"] = False if knowledge base cannot answer,
    signalling the orchestrator to cascade to the Web Search Agent.
    """
    state["current_node"] = "RAG_AGENT"
    state["rag_sufficient"] = True  # assume sufficient unless proven otherwise

    messages = state.get("messages", [])
    session_id = state.get("session_id", "")

    last_user_msg = next(
        (m for m in reversed(messages) if m.get("role") == "user"), None
    )
    if not last_user_msg:
        return state

    user_query = last_user_msg.get("content", "")
    tl = user_query.lower()

    # Build conversation context block
    context_block = build_context_block(
        messages[:-1],  # exclude the message we're about to answer
        conversation_summary=state.get("conversation_summary", ""),
        last_n=5,
    )

    # ── Offer / contract review detection ─────────────────────────────────────
    offer_kw = [
        "contract", "offer", "agreement", "developer offer", "revenue share",
        "exit clause", "reversal clause", "who owns the credit", "signing",
        "review this offer", "review the contract", "review the agreement",
    ]
    if any(kw in tl for kw in offer_kw):
        return await _handle_offer_review(state, user_query, context_block)

    # ── RAG retrieval with agentic loop ───────────────────────────────────────
    chunks = await _retrieve_with_agentic_loop(user_query)
    state["rag_citations"] = [c.chunk_id for c in chunks]

    # ── Check if retrieval was actually useful ────────────────────────────────
    if not _chunks_are_useful(chunks):
        logger.info(f"RAG: no useful chunks found for: {user_query[:80]}")
        await log_unanswerable_question(
            session_id=session_id,
            question=user_query,
            node="rag_agent",
            reason="No matching chunks above relevance threshold",
        )
        state["rag_sufficient"] = False
        # Do NOT append a reply — the graph will cascade to Web Search Agent
        return state

    # ── Generate answer from retrieved context ─────────────────────────────────
    context_text = _format_chunks(chunks)
    prompt = (
        f"{context_block}\n\n"
        f"User Question: {user_query}\n\n"
        f"Retrieved Knowledge Base Context:\n{context_text}\n\n"
        "Answer the question accurately and helpfully, referencing source document names for specific claims. "
        "Use the conversation context to make your response relevant to what the user already knows."
    )

    try:
        output = await llm_caller.call_with_schema(
            prompt=prompt,
            schema=RAGAnswer,
            system_prompt=RAG_ANSWER_SYSTEM,
        )

        reply = output.answer
        if output.last_verified_date:
            reply += f"\n\n*Sources last verified: {output.last_verified_date}*"
        reply += f"\n\n_{output.disclaimer}_"

        state["messages"].append({"role": "assistant", "content": reply})

    except Exception as e:
        logger.error(f"RAG answer generation failed: {e}")
        await log_unanswerable_question(
            session_id=session_id,
            question=user_query,
            node="rag_agent",
            reason=f"LLM generation failed: {str(e)[:100]}",
        )
        # Cascade to web search
        state["rag_sufficient"] = False

    return state
