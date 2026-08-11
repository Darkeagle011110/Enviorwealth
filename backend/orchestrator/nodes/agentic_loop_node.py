import logging
from orchestrator.state import ConversationState
from orchestrator.llm_schemas import AgenticCriticOutput, FactualAnswer
from orchestrator.llm_caller import llm_caller
from rag.retriever import Retriever

logger = logging.getLogger(__name__)

CRITIC_SYSTEM_PROMPT = """You are evaluating if retrieved context answers a complex edge-case question.
If the context is sufficient, output is_grounded=True.
If it is insufficient, output is_grounded=False, explain what is missing, and provide a revised search query to find it.
"""

ANSWER_SYSTEM_PROMPT = """You are answering a complex edge-case question about carbon credits.
Answer based ONLY on the provided context. Cite Source Chunk IDs for specific claims.
"""

MAX_ITERATIONS = 3

async def agentic_loop_node(state: ConversationState) -> ConversationState:
    """
    Handles complex edge cases by iteratively retrieving and evaluating context 
    up to a maximum number of iterations.
    """
    state["current_node"] = "EDGE_CASE"
    
    if not state.get("messages"):
        return state
        
    original_query = state["messages"][-1]["content"]
    current_query = original_query
    
    retriever = Retriever()
    accumulated_chunks = []
    
    for i in range(MAX_ITERATIONS):
        logger.info(f"Agentic loop iteration {i+1} for query: {current_query}")
        
        # 1. Retrieve
        chunks = await retriever.search(current_query, top_k=3)
        if chunks:
            accumulated_chunks.extend(chunks)
            
        if not accumulated_chunks:
            break
            
        # Deduplicate chunks
        seen = set()
        unique_chunks = []
        for c in accumulated_chunks:
            if c.chunk_id not in seen:
                seen.add(c.chunk_id)
                unique_chunks.append(c)
        accumulated_chunks = unique_chunks
            
        context_text = "\n\n".join([f"[{c.chunk_id}] {c.text}" for c in accumulated_chunks])
        
        # 2. Critic Step
        critic_prompt = (
            f"Original Question: {original_query}\n\n"
            f"Accumulated Context:\n{context_text}\n\n"
            f"Evaluate if this context is sufficient."
        )
        
        try:
            critic_output = await llm_caller.call_with_schema(
                prompt=critic_prompt,
                schema=AgenticCriticOutput,
                system_prompt=CRITIC_SYSTEM_PROMPT
            )
            
            if critic_output.is_grounded:
                logger.info("Critic approved context.")
                break
            else:
                logger.info(f"Critic rejected context. Missing: {critic_output.missing_information}")
                if critic_output.revised_search_query:
                    current_query = critic_output.revised_search_query
                else:
                    break # Nowhere else to look
                    
        except Exception as e:
            logger.error(f"Critic failed: {e}")
            break
            
    # 3. Generate Final Answer
    if not accumulated_chunks:
        state["messages"].append({"role": "assistant", "content": "I don't have enough specific information to answer that complex edge case confidently."})
        return state
        
    context_text = "\n\n".join([f"[Source Chunk ID: {c.chunk_id}] {c.text}" for c in accumulated_chunks])
    answer_prompt = (
        f"Question: {original_query}\n\n"
        f"Context:\n{context_text}\n\n"
        f"Answer the question, citing sources."
    )
    
    try:
        qa_output = await llm_caller.call_with_schema(
            prompt=answer_prompt,
            schema=FactualAnswer,
            system_prompt=ANSWER_SYSTEM_PROMPT
        )
        
        state["rag_citations"] = qa_output.source_chunk_ids
        state["messages"].append({"role": "assistant", "content": f"{qa_output.answer}\n\n_{qa_output.disclaimer}_"})
        
    except Exception as e:
        logger.error(f"Agentic final answer failed: {e}")
        state["messages"].append({"role": "assistant", "content": "An error occurred while generating the detailed answer."})
        
    return state
