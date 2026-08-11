from orchestrator.state import ConversationState

def greeting_node(state: ConversationState) -> ConversationState:
    """
    Handles the GREETING state. Sends a warm consultant-style welcome.
    Does NOT start intake screening — the user must explicitly ask to check eligibility.
    """
    welcome_msg = (
        "Hello! I'm EnviroWealth's carbon credit consultant. 🌱\n\n"
        "I can help you with:\n"
        "- **Learning** about how carbon credits work in India\n"
        "- **Checking** if your land is eligible for a carbon project\n"
        "- **Reviewing** a contract offer you've received from a developer\n"
        "- **Understanding** the economics and timelines involved\n\n"
        "Just ask me anything — or if you'd like to check your land's eligibility, "
        "say **\"Check my eligibility\"** and I'll walk you through a quick 6-question screening."
    )

    if not state.get("messages"):
        state["messages"] = []

    state["messages"].append({"role": "assistant", "content": welcome_msg})

    # Initialize fields
    if "intake_data" not in state or not state["intake_data"]:
        state["intake_data"] = {}

    state["screening_started"] = False
    state["current_node"] = "GREETING"
    state["ui_state"] = {"stage": "consulting"}
    return state
