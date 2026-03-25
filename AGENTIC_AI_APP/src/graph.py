from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import AIMessage

class State(TypedDict):
    messages: Annotated[list, add_messages]

def chatbot(state: State):
    # Retrieve the last message from the user
    user_message = state["messages"][-1].content
    # Generate a dummy response incorporating the history length to prove checkpointer isolation
    user_msg_count = len([m for m in state["messages"] if m.type == "human"])
    response_text = f"Agent: I heard '{user_message}'. You have sent {user_msg_count} messages in this thread."
    return {"messages": [AIMessage(content=response_text)]}

graph_builder = StateGraph(State)
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_edge(START, "chatbot")
graph_builder.add_edge("chatbot", END)

# The adapter will compile it with a checkpointer
def get_graph(checkpointer=None):
    if checkpointer:
        return graph_builder.compile(checkpointer=checkpointer)
    return graph_builder.compile()

graph = get_graph()
