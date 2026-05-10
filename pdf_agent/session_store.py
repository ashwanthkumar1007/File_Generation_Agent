"""In-memory session store for multi-turn conversations."""

from __future__ import annotations

from pdf_agent.graph.state import PDFAgentState


_sessions: dict[str, PDFAgentState] = {}


def get_or_create(thread_id: str) -> PDFAgentState:
    if thread_id not in _sessions:
        _sessions[thread_id] = PDFAgentState(
            messages=[],
            intent="",
            renderer=None,
            document_category=None,
            document_spec=None,
            pdf_path=None,
            chat_response=None,
            error=None,
        )
    return _sessions[thread_id]


def update(thread_id: str, result: dict) -> PDFAgentState:
    state = _sessions[thread_id]
    state["document_spec"] = result.get("document_spec", state["document_spec"])
    state["pdf_path"] = result.get("pdf_path", state["pdf_path"])
    state["chat_response"] = result.get("chat_response")
    state["messages"] = result.get("messages", state["messages"])
    state["error"] = result.get("error")
    state["intent"] = result.get("intent", state.get("intent", ""))
    state["renderer"] = result.get("renderer", state.get("renderer"))
    state["document_category"] = result.get(
        "document_category", state.get("document_category")
    )
    return state
