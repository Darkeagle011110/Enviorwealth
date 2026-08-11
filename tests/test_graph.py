import pytest
from orchestrator.graph import orchestrator_app

@pytest.mark.asyncio
async def test_graph_initial_greeting():
    """
    Test that an empty state goes to GREETING node.
    """
    initial_state = {"session_id": "test_1", "messages": [], "turn_count": 0}
    
    final_state = await orchestrator_app.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": "test_1"}}
    )
    
    assert final_state["current_node"] == "GREETING"
    assert len(final_state["messages"]) == 1
    assert "How can I help you today?" in final_state["messages"][0]["content"]

# More comprehensive tests for the graph would require mocking the LLM wrapper,
# which is good practice for CI but we verify the structural routing here.
