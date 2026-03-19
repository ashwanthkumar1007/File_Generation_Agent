"""Guide: Implementing Renderer-Specific Nodes

This guide shows how to extend the graph with renderer-specific implementations
that route dynamically based on the selected renderer from select_renderer.

## Current Flow:

classify_intent → select_renderer → generate_content → render_pdf (or apply_edit)

## Target Flow with Multiple Renderers:

classify_intent → select_renderer → generate_content → [fpdf2|weasyprint|borb|markdown]

"""

# ═══════════════════════════════════════════════════════════════════════════

# Step 1: Create Renderer-Specific Node Implementations

# ═══════════════════════════════════════════════════════════════════════════

# Example: pdf_agent/nodes/render_fpdf2.py

"""
from **future** import annotations

from pathlib import Path
from fpdf import FPDF

from pdf_agent.config import AgentConfig
from pdf_agent.graph.state import PDFAgentState
from pdf_agent.utils.logger import get_logger

logger = get_logger(**name**)

def render_fpdf2(state: PDFAgentState, \*, config: AgentConfig) -> dict:
'''Render PDF using FPDF2 for simple, templated layouts.'''

    logger.info("Rendering with FPDF2")

    document_spec = state.get("document_spec")
    if not document_spec:
        return {"error": "No document spec available"}

    # Create PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Title
    title = document_spec.get("title", "Document")
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, title, ln=True, align='C')
    pdf.ln(10)

    # Sections
    for section in document_spec.get("sections", []):
        section_type = section.get("type")
        content = section.get("content")

        if section_type == "heading":
            pdf.set_font('Arial', 'B', 14)
            pdf.cell(0, 10, content, ln=True)
            pdf.ln(5)

        elif section_type == "paragraph":
            pdf.set_font('Arial', '', 12)
            pdf.multi_cell(0, 10, content)
            pdf.ln(5)

        elif section_type == "bullet":
            pdf.set_font('Arial', '', 12)
            for item in content:
                pdf.cell(10, 10, '•')
                pdf.multi_cell(0, 10, item)
            pdf.ln(5)

        elif section_type == "table":
            # Simple table rendering
            headers = content.get("headers", [])
            rows = content.get("rows", [])

            pdf.set_font('Arial', 'B', 10)
            col_width = pdf.w / (len(headers) + 0.5)
            for header in headers:
                pdf.cell(col_width, 10, str(header), border=1)
            pdf.ln()

            pdf.set_font('Arial', '', 10)
            for row in rows:
                for cell in row:
                    pdf.cell(col_width, 10, str(cell), border=1)
                pdf.ln()
            pdf.ln(5)

    # Save
    output_path = Path(config.output_dir) / f"{title.replace(' ', '_')}_fpdf2.pdf"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(output_path)

    logger.info(f"FPDF2 PDF created: {output_path}")

    return {
        "pdf_path": str(output_path),
        "chat_response": f"✅ PDF created with FPDF2: {output_path.name}"
    }

"""

# ═══════════════════════════════════════════════════════════════════════════

# Step 2: Register Node in Graph

# ═══════════════════════════════════════════════════════════════════════════

"""
In pdf_agent/graph/pdf_agent_graph.py:

1. Import the new renderer node:
   from pdf_agent.nodes.render_fpdf2 import render_fpdf2

2. Register the node:
   graph.add_node("render_fpdf2", partial(render_fpdf2, config=config))

3. Same for other renderers:
   from pdf_agent.nodes.render_borb import render_borb
   from pdf_agent.nodes.render_markdown import render_markdown
   graph.add_node("render_borb", partial(render_borb, config=config))
   graph.add_node("render_markdown", partial(render_markdown, config=config))
   """

# ═══════════════════════════════════════════════════════════════════════════

# Step 3: Update Routing Logic

# ═══════════════════════════════════════════════════════════════════════════

"""
In pdf_agent/graph/pdf_agent_graph.py, update \_route_by_renderer:

def \_route_by_renderer(state: PDFAgentState) -> str:
'''Route to specific renderer implementation based on selected renderer.'''
renderer = state.get("renderer", "weasyprint")
logger.info(f"Routing to renderer: {renderer}")

    # Renderer-specific routing map
    renderer_node_map = {
        "weasyprint": "render_pdf",      # Existing weasyprint node
        "fpdf2": "render_fpdf2",         # NEW: FPDF2 node
        "borb": "render_borb",           # NEW: Borb node
        "markdown": "render_markdown",   # NEW: Markdown node
    }

    node_name = renderer_node_map.get(renderer, "render_pdf")

    if renderer not in renderer_node_map:
        logger.warning(f"Unknown renderer '{renderer}', falling back to weasyprint")

    return node_name

"""

# ═══════════════════════════════════════════════════════════════════════════

# Step 4: Replace Direct Edge with Conditional Routing

# ═══════════════════════════════════════════════════════════════════════════

"""
In pdf_agent/graph/pdf_agent_graph.py, replace:

    # OLD: Direct edge
    graph.add_edge("generate_content", "render_pdf")

With:

    # NEW: Conditional routing based on renderer
    graph.add_conditional_edges(
        "generate_content",
        _route_by_renderer,
        {
            "render_pdf": "render_pdf",          # weasyprint
            "render_fpdf2": "render_fpdf2",      # fpdf2
            "render_borb": "render_borb",        # borb
            "render_markdown": "render_markdown", # markdown
        },
    )

    # All renderers terminate
    graph.add_edge("render_pdf", END)
    graph.add_edge("render_fpdf2", END)
    graph.add_edge("render_borb", END)
    graph.add_edge("render_markdown", END)

"""

# ═══════════════════════════════════════════════════════════════════════════

# Step 5: Handle Edit Flow

# ═══════════════════════════════════════════════════════════════════════════

"""
For edit operations, you need to route through apply_edit first, then to the
appropriate renderer. Update the routing:

def \_route_after_generate(state: PDFAgentState) -> str:
'''Route after content generation.'''
intent = state.get("intent")

    if intent == "edit" and state.get("document_spec") is not None:
        logger.debug("Routing to apply_edit for iterative refinement")
        return "apply_edit"

    # For create operations, route to specific renderer
    renderer = state.get("renderer", "weasyprint")
    logger.debug(f"Routing to {renderer} for initial generation")

    # Map renderer to node name
    renderer_node_map = {
        "weasyprint": "render_pdf",
        "fpdf2": "render_fpdf2",
        "borb": "render_borb",
        "markdown": "render_markdown",
    }

    return renderer_node_map.get(renderer, "render_pdf")

Then add conditional edges:

    graph.add_conditional_edges(
        "generate_content",
        _route_after_generate,
        {
            "render_pdf": "render_pdf",
            "render_fpdf2": "render_fpdf2",
            "render_borb": "render_borb",
            "render_markdown": "render_markdown",
            "apply_edit": "apply_edit",
        },
    )

    # After edit, route to appropriate renderer
    graph.add_conditional_edges(
        "apply_edit",
        _route_by_renderer,
        {
            "render_pdf": "render_pdf",
            "render_fpdf2": "render_fpdf2",
            "render_borb": "render_borb",
            "render_markdown": "render_markdown",
        },
    )

"""

# ═══════════════════════════════════════════════════════════════════════════

# Complete Example: Final Graph Structure

# ═══════════════════════════════════════════════════════════════════════════

"""
from functools import partial
from langgraph.graph import END, StateGraph

from pdf_agent.graph.state import PDFAgentState
from pdf_agent.nodes.classify_intent import classify_intent
from pdf_agent.nodes.select_renderer import select_renderer
from pdf_agent.nodes.generate_content import generate_content
from pdf_agent.nodes.apply_edit import apply_edit
from pdf_agent.nodes.chat_response import chat_response

# Renderer implementations

from pdf_agent.nodes.render_pdf import render_pdf # weasyprint
from pdf_agent.nodes.render_fpdf2 import render_fpdf2 # NEW
from pdf_agent.nodes.render_borb import render_borb # NEW
from pdf_agent.nodes.render_markdown import render_markdown # NEW

def build_graph(llm, config):
graph = StateGraph(PDFAgentState)

    # ═══════════════════════════════════════════════════════════════════════
    # Nodes
    # ═══════════════════════════════════════════════════════════════════════
    graph.add_node("classify_intent", partial(classify_intent, llm=llm))
    graph.add_node("select_renderer", partial(select_renderer, llm=llm))
    graph.add_node("generate_content", partial(generate_content, llm=llm))
    graph.add_node("apply_edit", partial(apply_edit, llm=llm))
    graph.add_node("chat_response", partial(chat_response, llm=llm))

    # Renderer nodes
    graph.add_node("render_pdf", partial(render_pdf, config=config))
    graph.add_node("render_fpdf2", partial(render_fpdf2, config=config))
    graph.add_node("render_borb", partial(render_borb, config=config))
    graph.add_node("render_markdown", partial(render_markdown, config=config))

    # ═══════════════════════════════════════════════════════════════════════
    # Edges
    # ═══════════════════════════════════════════════════════════════════════
    graph.set_entry_point("classify_intent")

    # Route by intent
    graph.add_conditional_edges(
        "classify_intent",
        _route_by_intent,
        {
            "select_renderer": "select_renderer",
            "chat_response": "chat_response",
        },
    )

    # Always generate content after selecting renderer
    graph.add_edge("select_renderer", "generate_content")

    # Route to renderer based on selection
    graph.add_conditional_edges(
        "generate_content",
        _route_by_renderer_and_intent,
        {
            "render_pdf": "render_pdf",
            "render_fpdf2": "render_fpdf2",
            "render_borb": "render_borb",
            "render_markdown": "render_markdown",
            "apply_edit": "apply_edit",
        },
    )

    # After edit, route to renderer
    graph.add_conditional_edges(
        "apply_edit",
        _route_by_renderer,
        {
            "render_pdf": "render_pdf",
            "render_fpdf2": "render_fpdf2",
            "render_borb": "render_borb",
            "render_markdown": "render_markdown",
        },
    )

    # Terminal edges
    graph.add_edge("render_pdf", END)
    graph.add_edge("render_fpdf2", END)
    graph.add_edge("render_borb", END)
    graph.add_edge("render_markdown", END)
    graph.add_edge("chat_response", END)

    return graph.compile()

"""

# ═══════════════════════════════════════════════════════════════════════════

# Testing Individual Renderers

# ═══════════════════════════════════════════════════════════════════════════

"""

# Test FPDF2 renderer selection

from langchain_core.messages import HumanMessage

result = graph.invoke({
"messages": [HumanMessage(content="Create an invoice for $500")],
"intent": None,
"renderer": None,
"document_spec": None,
"pdf_path": None,
"chat_response": None,
"error": None
})

print(f"Selected: {result['renderer']}") # Should be 'fpdf2'
print(f"Output: {result['pdf_path']}") # Should end with \_fpdf2.pdf

# Test WeasyPrint renderer selection

result = graph.invoke({
"messages": [HumanMessage(content="Create a branded business proposal")], # ... other state fields
})

print(f"Selected: {result['renderer']}") # Should be 'weasyprint'
print(f"Output: {result['pdf_path']}") # Should be from weasyprint
"""

# ═══════════════════════════════════════════════════════════════════════════

# Summary of Changes

# ═══════════════════════════════════════════════════════════════════════════

"""

1. ✅ Create renderer-specific node files (render_fpdf2.py, render_borb.py, etc.)
2. ✅ Import and register nodes in build_graph()
3. ✅ Update \_route_by_renderer() to map renderer names to nodes
4. ✅ Replace direct edge with conditional routing
5. ✅ Add terminal edges for all new renderers
6. ✅ Test each renderer with appropriate prompts

Benefits:

- Select_renderer automatically chooses best renderer via LLM
- Generate_content is aware of selected renderer
- Each renderer has specialized implementation
- Easy to add new renderers without changing core logic
- Maintains backward compatibility (weasyprint as default)
  """
