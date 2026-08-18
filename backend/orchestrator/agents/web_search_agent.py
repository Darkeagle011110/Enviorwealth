"""
web_search_agent.py — DuckDuckGo web search fallback agent.

Triggered by the orchestrator graph when the RAG agent sets
state["rag_sufficient"] = False (no useful chunks in the knowledge base).

Searches DuckDuckGo for current carbon credit information, scoped to
the carbon markets / environmental regulations domain only.

No caching layer — every search is fresh.
"""
import logging
from typing import List
from pydantic import BaseModel, Field
from typing import Optional

from orchestrator.state import ConversationState
from orchestrator.llm_caller import llm_caller
from orchestrator.agents.context_manager import build_context_block

logger = logging.getLogger(__name__)

# Domain scope appended to all search queries to keep results relevant
DOMAIN_SCOPE = "carbon credits India CCTS"
MAX_SEARCH_RESULTS = 6   # snippets to pass to LLM
MAX_SNIPPET_CHARS = 400  # truncate each snippet to limit tokens


# ─── Pydantic schemas ─────────────────────────────────────────────────────────

class WebSearchAnswer(BaseModel):
    answer: str = Field(..., description="Answer synthesised from web search results.")
    sources: List[str] = Field(default_factory=list, description="Source URLs used.")
    disclaimer: str = Field(
        ...,
        description="Disclaimer noting the information is from web search and may not be fully verified.",
    )
    suggest_eligibility_check: bool = Field(
        False,
        description=(
            "Set to true if, based on the full conversation context, the user seems to be "
            "moving towards wanting to check whether THEIR OWN land or project is eligible "
            "for carbon credits. For example: they asked about eligibility criteria, "
            "which types of land qualify, what is needed to get carbon credits, etc., "
            "and have NOT yet started the screening process. "
            "Set to false if the question is purely informational with no personal intent, "
            "or if the user is already in the middle of a screening."
        ),
    )


class SearchQueryRefinement(BaseModel):
    refined_query: str = Field(
        ...,
        description="A concise, specific web search query for this carbon credit question.",
    )


# ─── System prompts ───────────────────────────────────────────────────────────

QUERY_REFINE_SYSTEM = """You are creating an optimal web search query for a carbon credit question.
The query must be specific, technical, and scoped to carbon credits, climate finance, or Indian
environmental regulations. Output a single search query string — no explanation, no quotes around it.
Aim for 5-10 words that a domain expert would search.
"""

WEB_ANSWER_SYSTEM = """You are EnviroWealth's carbon credit consultant synthesising an answer
from web search results. The user's knowledge base did not have a good answer, so you are using
live web results.

Rules:
- Synthesise the search results into a clear, helpful answer.
- Cite specific sources (URLs) for key claims.
- Do NOT invent information not present in the search results.
- Be clear that this comes from web search and may need verification against primary sources.
- Always end with the disclaimer provided.
- Do NOT give legal or financial advice.

Eligibility CTA Decision (suggest_eligibility_check field):
- Read the FULL conversation history carefully.
- Set suggest_eligibility_check = true if the user's message (or the conversation trajectory)
  suggests they are interested in whether THEIR OWN land, project, or situation qualifies
  for carbon credits. Signs: they asked about eligibility criteria, which lands qualify,
  what requirements exist, how to check if their land is eligible, etc.
- Set suggest_eligibility_check = false if:
  - The question is purely academic/informational with no personal application
  - The user is already undergoing screening (screening_started = true in context)
  - The user already has an eligibility offer pending (awaiting_eligibility_confirm = true)
  - The query has nothing to do with eligibility
"""

FALLBACK_REPLY = (
    "I wasn't able to find a good answer in my knowledge base, and my web search didn't return "
    "reliable results for this specific question.\n\n"
    "For the most current information, I'd recommend checking:\n"
    "- **CCTS / BEE**: [bee.gov.in](https://bee.gov.in)\n"
    "- **Verra Registry**: [registry.verra.org](https://registry.verra.org)\n"
    "- **Grid-India Registry**: [ghgregistry.grid.in](https://ghgregistry.grid.in)\n\n"
    "_This is educational information only — not legal or financial advice._"
)


# ─── DuckDuckGo search helper ─────────────────────────────────────────────────

async def _duckduckgo_search(query: str) -> List[dict]:
    """
    Perform a DuckDuckGo text search and return a list of result dicts
    with keys: title, href, body.

    Returns [] if the library is unavailable or the search fails.
    """
    try:
        from ddgs import DDGS  # renamed from duckduckgo_search → ddgs
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=MAX_SEARCH_RESULTS):
                results.append(r)
        logger.info(f"DuckDuckGo returned {len(results)} results for: '{query[:80]}'")
        return results
    except ImportError:
        logger.error(
            "ddgs package not installed. Run: pip install ddgs"
        )
        return []
    except Exception as e:
        logger.error(f"DuckDuckGo search failed for '{query[:80]}': {e}")
        return []


def _build_search_context(results: List[dict]) -> str:
    """Format search results into a compact context block."""
    lines = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "")
        url = r.get("href", "")
        body = r.get("body", "")[:MAX_SNIPPET_CHARS]
        lines.append(f"[{i}] {title}\nURL: {url}\n{body}")
    return "\n\n".join(lines)


# ─── Main web search agent ────────────────────────────────────────────────────

async def web_search_agent(state: ConversationState) -> ConversationState:
    """
    Searches DuckDuckGo for the user's query when the RAG knowledge base
    was insufficient. Synthesises search results into a coherent answer
    with source attribution.
    """
    state["current_node"] = "WEB_SEARCH_AGENT"

    messages = state.get("messages", [])
    last_user_msg = next(
        (m for m in reversed(messages) if m.get("role") == "user"), None
    )
    if not last_user_msg:
        return state

    user_query = last_user_msg.get("content", "")
    context_block = build_context_block(
        messages[:-1],
        conversation_summary=state.get("conversation_summary", ""),
        last_n=3,
    )

    # ── Step 1: Refine the query for optimal web search ────────────────────────
    try:
        refine_output = await llm_caller.call_with_schema(
            prompt=(
                f"User's question: {user_query}\n\n"
                f"Context: {context_block[:500]}\n\n"
                "Create an optimal web search query to answer this question."
            ),
            schema=SearchQueryRefinement,
            system_prompt=QUERY_REFINE_SYSTEM,
        )
        search_query = f"{refine_output.refined_query} {DOMAIN_SCOPE}"
    except Exception as e:
        logger.warning(f"Query refinement failed: {e}. Using raw query.")
        search_query = f"{user_query[:150]} {DOMAIN_SCOPE}"

    logger.info(f"Web search query: '{search_query}'")

    # ── Step 2: Perform DuckDuckGo search ─────────────────────────────────────
    results = await _duckduckgo_search(search_query)

    if not results:
        logger.warning("Web search returned no results. Sending fallback reply.")
        state["messages"].append({"role": "assistant", "content": FALLBACK_REPLY})
        return state

    # ── Step 3: Synthesise answer from search results ─────────────────────────
    search_context = _build_search_context(results)
    source_urls = [r.get("href", "") for r in results if r.get("href")]

    prompt = (
        f"{context_block}\n\n"
        f"State: screening_started={state.get('screening_started', False)}, "
        f"awaiting_eligibility_confirm={state.get('awaiting_eligibility_confirm', False)}\n\n"
        f"User Question: {user_query}\n\n"
        f"Web Search Results:\n{search_context}\n\n"
        "Synthesise a helpful answer from these search results. "
        "Cite specific source URLs for key claims. "
        "Note that these results come from a live web search and should be verified against primary sources. "
        "Also decide, based on the full conversation above, whether to set suggest_eligibility_check."
    )

    try:
        output = await llm_caller.call_with_schema(
            prompt=prompt,
            schema=WebSearchAnswer,
            system_prompt=WEB_ANSWER_SYSTEM,
        )

        reply = output.answer

        if output.sources:
            formatted_sources = "\n".join(f"- {url}" for url in output.sources[:4])
            reply += f"\n\n**Sources (web search):**\n{formatted_sources}"
        elif source_urls:
            formatted_sources = "\n".join(f"- {url}" for url in source_urls[:4])
            reply += f"\n\n**Sources (web search):**\n{formatted_sources}"

        reply += f"\n\n_{output.disclaimer}_"

        # ── LLM-driven eligibility CTA (no keyword matching) ──────────────────────
        if output.suggest_eligibility_check:
            reply += (
                "\n\n**To check your own land's eligibility for carbon credits, "
                "just click the button below and fill out a short form — I'll give you "
                "an instant assessment.**"
            )
            state["awaiting_eligibility_confirm"] = True
            state["ui_state"] = {"action": "OFFER_ELIGIBILITY_CHECK"}

        state["messages"].append({"role": "assistant", "content": reply})

    except Exception as e:
        logger.error(f"Web search answer synthesis failed: {e}")
        state["messages"].append({"role": "assistant", "content": FALLBACK_REPLY})

    return state
