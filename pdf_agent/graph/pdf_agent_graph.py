"""LangGraph workflow for the PDF agent.

Graph topology:

    user message
         │
         ▼
    classify_intent
         │
    ┌────┼─────────┐
    │                  │
  create/edit           chat
    │                  │
    ▼                  ▼
select_renderer    chat_response
    │                  │
    ▼                 END
generate_content
    │
    ├──────┬──────┬──────┬──────┐
    ▼      ▼      ▼      ▼      ▼
weasy  fpdf2  borb  markdown apply_edit
                                   │
                    ┌────────────┴
                    ▼  (same renderer as was selected)
                [render_*]
                    │
                   END
"""

from __future__ import annotations

from functools import partial
from typing import Literal

from langgraph.graph import END, StateGraph

from pdf_agent.config import AgentConfig
from pdf_agent.graph.state import PDFAgentState
from pdf_agent.nodes.apply_edit import apply_edit
from pdf_agent.nodes.chat_response import chat_response
from pdf_agent.nodes.classify_intent import classify_intent
from pdf_agent.nodes.generate_content import generate_content
from pdf_agent.nodes.render_weasy import render_weasy
from pdf_agent.nodes.render_fpdf2 import render_fpdf2
from pdf_agent.nodes.render_borb import render_borb
from pdf_agent.nodes.render_markdown import render_markdown
from pdf_agent.nodes.select_renderer import select_renderer

from langchain_core.language_models import BaseChatModel
from pdf_agent.utils.logger import get_logger

logger = get_logger(__name__)

# Maps renderer name → graph node name (single source of truth)
_RENDERER_NODE_MAP: dict[str, str] = {
    "weasyprint": "render_weasy",
    "fpdf2":      "render_fpdf2",
    "borb":       "render_borb",
    "markdown":   "render_markdown",
}


def _route_by_intent(
    state: PDFAgentState,
) -> Literal["select_renderer", "chat_response"]:
    """Route to the correct node based on classified intent."""
    intent = state.get("intent")
    if intent == "chat":
        return "chat_response"
    # Both create and edit go through select_renderer
    return "select_renderer"


def _route_after_generate(state: PDFAgentState) -> str:
    """Route after content generation.
    
    - edit intent with an existing spec  → apply_edit first
    - create intent (or edit without prior spec) → straight to renderer
    """
    intent = state.get("intent")
    if intent == "edit" and state.get("document_spec") is not None:
        logger.debug("Routing to apply_edit for iterative refinement")
        return "apply_edit"
    renderer = state.get("renderer", "weasyprint")
    node = _RENDERER_NODE_MAP.get(renderer, "render_weasy")
    logger.debug("Routing to %s after content generation", node)
    return node


def _route_after_edit(state: PDFAgentState) -> str:
    """Route to the appropriate renderer after apply_edit."""
    renderer = state.get("renderer", "weasyprint")
    node = _RENDERER_NODE_MAP.get(renderer, "render_weasy")
    logger.debug("Routing to %s after apply_edit", node)
    return node


def build_graph(llm: BaseChatModel, config: AgentConfig) -> StateGraph:
    """Construct and compile the PDF agent LangGraph.

    Parameters
    ----------
    llm:
        The chat model used by LLM-powered nodes.
    config:
        Agent configuration (paths, defaults, etc.).

    Returns
    -------
    Compiled LangGraph ready for ``.invoke()`` or ``.stream()``.
    """
    graph = StateGraph(PDFAgentState)

    # ══════════════════════════════════════════════════════════════════════
    # Nodes
    # ══════════════════════════════════════════════════════════════════════
    graph.add_node("classify_intent", partial(classify_intent, llm=llm))
    graph.add_node("select_renderer", partial(select_renderer, llm=llm))
    graph.add_node("generate_content", partial(generate_content, llm=llm))
    graph.add_node("apply_edit",       partial(apply_edit, llm=llm))
    graph.add_node("chat_response",    partial(chat_response, llm=llm))
    # Renderer nodes — one per backend
    graph.add_node("render_weasy",    partial(render_weasy,    config=config))
    graph.add_node("render_fpdf2",    partial(render_fpdf2,    config=config))
    graph.add_node("render_borb",     partial(render_borb,     config=config))
    graph.add_node("render_markdown", partial(render_markdown, config=config))

    # ══════════════════════════════════════════════════════════════════════
    # Entry point
    # ══════════════════════════════════════════════════════════════════════
    graph.set_entry_point("classify_intent")

    # ══════════════════════════════════════════════════════════════════════
    # Edges
    # ══════════════════════════════════════════════════════════════════════

    # classify_intent → select_renderer | chat_response
    graph.add_conditional_edges(
        "classify_intent",
        _route_by_intent,
        {
            "select_renderer": "select_renderer",
            "chat_response":   "chat_response",
        },
    )

    # select_renderer → generate_content (always)
    graph.add_edge("select_renderer", "generate_content")

    # generate_content → apply_edit | render_weasy | render_fpdf2 | ...
    _all_render_targets = {v: v for v in _RENDERER_NODE_MAP.values()}
    graph.add_conditional_edges(
        "generate_content",
        _route_after_generate,
        {"apply_edit": "apply_edit", **_all_render_targets},
    )

    # apply_edit → render_weasy | render_fpdf2 | render_borb | render_markdown
    graph.add_conditional_edges(
        "apply_edit",
        _route_after_edit,
        _all_render_targets,
    )

    # ══════════════════════════════════════════════════════════════════════
    # Terminal edges — every render node and chat ends here
    # ══════════════════════════════════════════════════════════════════════
    for render_node in _RENDERER_NODE_MAP.values():
        graph.add_edge(render_node, END)
    graph.add_edge("chat_response", END)

    return graph.compile()
