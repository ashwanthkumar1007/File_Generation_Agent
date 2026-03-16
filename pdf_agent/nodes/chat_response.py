"""Node: answer a general question directly — no PDF produced.

Streams tokens to stdout in real-time and accumulates the full reply
into state so downstream code can reference it if needed.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.language_models import BaseChatModel

from pdf_agent.graph.state import PDFAgentState
from pdf_agent.utils.logger import get_logger

logger = get_logger(__name__)


SYSTEM_PROMPT = SystemMessage(content="""\
You are a helpful AI assistant embedded inside a PDF document generation tool.
Answer the user's question clearly and concisely.
If the question seems related to document generation, you may mention that the
user can ask you to create or edit a PDF at any time.
""")


def chat_response(state: PDFAgentState, *, llm: BaseChatModel) -> dict:
    """Stream a conversational reply for general questions.

    Tokens are written to stdout as they arrive so the user sees a live
    response.  The complete reply is also stored in ``state["chat_response"]``
    and appended to the message history.
    """
    messages = [SYSTEM_PROMPT, *state["messages"]]

    full_response = ""
    logger.info("Streaming chat response")
    print("\nAssistant: ", end="", flush=True)

    for chunk in llm.stream(messages):
        token: str = chunk.content or ""
        print(token, end="", flush=True)
        full_response += token

    print("\n")  # newline after stream ends

    return {
        "chat_response": full_response,
        "messages": [
            *state["messages"],
            AIMessage(content=full_response),
        ],
        "error": None,
    }
