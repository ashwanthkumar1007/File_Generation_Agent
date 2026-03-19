"""Example: Integrating select_renderer into your LangGraph.

This demonstrates how to wire the select_renderer node into your PDF agent
graph and route to specific renderer implementations.
"""

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage

from pdf_agent.graph.state import PDFAgentState
from pdf_agent.nodes.select_renderer import select_renderer
from pdf_agent.nodes.classify_intent import classify_intent
# Import your renderer implementations
# from pdf_agent.nodes.render_with_weasyprint import render_with_weasyprint
# from pdf_agent.nodes.render_with_fpdf2 import render_with_fpdf2
# etc.


def build_graph(llm):
    """Build the PDF agent graph with dynamic renderer selection."""
    
    workflow = StateGraph(PDFAgentState)
    
    # ═══════════════════════════════════════════════════════════════════
    # 1. Add all nodes
    # ═══════════════════════════════════════════════════════════════════
    
    workflow.add_node("classify_intent", lambda state: classify_intent(state, llm))
    workflow.add_node("select_renderer", lambda state: select_renderer(state, llm))
    workflow.add_node("generate_content", lambda state: generate_content(state, llm))
    
    # Add renderer-specific nodes
    workflow.add_node("render_weasyprint", render_with_weasyprint)
    workflow.add_node("render_fpdf2", render_with_fpdf2)
    workflow.add_node("render_borb", render_with_borb)
    workflow.add_node("render_markdown", render_with_markdown)
    
    workflow.add_node("chat_response", lambda state: chat_response(state, llm))
    
    # ═══════════════════════════════════════════════════════════════════
    # 2. Define routing functions
    # ═══════════════════════════════════════════════════════════════════
    
    def route_by_intent(state: PDFAgentState) -> str:
        """Route based on classified intent."""
        intent = state["intent"]
        if intent in ("generate", "edit"):
            return "select_renderer"
        return "chat_response"
    
    def route_by_renderer(state: PDFAgentState) -> str:
        """Route to specific renderer based on selection."""
        renderer = state.get("renderer")
        
        # Map renderer names to node names
        renderer_map = {
            "weasyprint": "render_weasyprint",
            "fpdf2": "render_fpdf2",
            "borb": "render_borb",
            "markdown": "render_markdown",
        }
        
        node_name = renderer_map.get(renderer)
        if not node_name:
            raise ValueError(f"Unknown renderer: {renderer}")
        
        return node_name
    
    # ═══════════════════════════════════════════════════════════════════
    # 3. Add edges
    # ═══════════════════════════════════════════════════════════════════
    
    workflow.set_entry_point("classify_intent")
    
    # Conditional routing after intent classification
    workflow.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {
            "select_renderer": "select_renderer",
            "chat_response": "chat_response"
        }
    )
    
    # After selecting renderer, generate content
    workflow.add_edge("select_renderer", "generate_content")
    
    # After generating content, route to appropriate renderer
    workflow.add_conditional_edges(
        "generate_content",
        route_by_renderer,
        {
            "render_weasyprint": "render_weasyprint",
            "render_fpdf2": "render_fpdf2",
            "render_borb": "render_borb",
            "render_markdown": "render_markdown",
        }
    )
    
    # All renderers end the workflow
    workflow.add_edge("render_weasyprint", END)
    workflow.add_edge("render_fpdf2", END)
    workflow.add_edge("render_borb", END)
    workflow.add_edge("render_markdown", END)
    workflow.add_edge("chat_response", END)
    
    return workflow.compile()


# ═══════════════════════════════════════════════════════════════════════
# Example Renderer Node Implementations
# ═══════════════════════════════════════════════════════════════════════

def render_with_weasyprint(state: PDFAgentState) -> PDFAgentState:
    """Render PDF using WeasyPrint (HTML/CSS-based)."""
    from pdf_agent.rendering.pdf_renderer import render_pdf
    from pathlib import Path
    
    output_path = Path("output") / "document_weasyprint.pdf"
    result_path = render_pdf(state["document_spec"], output_path)
    
    return {
        "pdf_path": str(result_path),
        "chat_response": f"✅ Professional PDF created with WeasyPrint: {result_path.name}"
    }


def render_with_fpdf2(state: PDFAgentState) -> PDFAgentState:
    """Render PDF using FPDF2 (programmatic approach)."""
    from fpdf import FPDF
    from pathlib import Path
    
    output_path = Path("output") / "document_fpdf2.pdf"
    
    # Simple FPDF2 implementation
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    
    # Render document_spec to PDF
    for section in state["document_spec"].get("sections", []):
        pdf.cell(0, 10, section["heading"], ln=True)
        for item in section.get("items", []):
            pdf.set_font('Arial', '', 12)
            pdf.multi_cell(0, 10, item.get("text", ""))
    
    pdf.output(output_path)
    
    return {
        "pdf_path": str(output_path),
        "chat_response": f"✅ Document created with FPDF2: {output_path.name}"
    }


def render_with_borb(state: PDFAgentState) -> PDFAgentState:
    """Render PDF using Borb (advanced PDF features)."""
    from pathlib import Path
    # from borb.pdf import Document, Page, PDF
    # ... borb implementation
    
    output_path = Path("output") / "document_borb.pdf"
    
    # Placeholder implementation
    # In reality, you'd use borb's API here
    
    return {
        "pdf_path": str(output_path),
        "chat_response": f"✅ Advanced PDF created with Borb: {output_path.name}"
    }


def render_with_markdown(state: PDFAgentState) -> PDFAgentState:
    """Convert document to Markdown and optionally to PDF."""
    from pathlib import Path
    
    output_md = Path("output") / "document.md"
    output_pdf = Path("output") / "document_from_markdown.pdf"
    
    # Convert document_spec to markdown
    markdown_content = "# Document\n\n"
    for section in state["document_spec"].get("sections", []):
        markdown_content += f"## {section['heading']}\n\n"
        for item in section.get("items", []):
            text = item.get("text", "")
            if item.get("type") == "bullet":
                markdown_content += f"- {text}\n"
            else:
                markdown_content += f"{text}\n\n"
    
    # Save markdown
    output_md.write_text(markdown_content)
    
    # Optionally convert to PDF using pandoc or markdown library
    # For now, just return markdown path
    
    return {
        "pdf_path": str(output_md),
        "chat_response": f"✅ Markdown document created: {output_md.name}"
    }


# ═══════════════════════════════════════════════════════════════════════
# Placeholder implementations for completeness
# ═══════════════════════════════════════════════════════════════════════

def generate_content(state: PDFAgentState, llm) -> PDFAgentState:
    """Generate document content specification."""
    # Your existing generate_content implementation
    return {"document_spec": {"sections": []}}


def chat_response(state: PDFAgentState, llm) -> PDFAgentState:
    """Handle chat-only interactions."""
    # Your existing chat_response implementation
    return {"chat_response": "How can I help you?"}


# ═══════════════════════════════════════════════════════════════════════
# Usage Example
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from langchain_openai import ChatOpenAI
    
    # Initialize LLM (use your configured provider)
    llm = ChatOpenAI(model="gpt-4", temperature=0.7)
    
    # Build graph
    graph = build_graph(llm)
    
    # Test invoice generation (should select fpdf2)
    result = graph.invoke({
        "messages": [HumanMessage(content="Create an invoice for $500")],
        "intent": None,
        "renderer": None,
        "document_spec": None,
        "pdf_path": None,
        "chat_response": None,
        "error": None
    })
    
    print(f"Selected renderer: {result.get('renderer')}")
    print(f"Output: {result.get('chat_response')}")
    
    # Test branded report (should select weasyprint)
    result = graph.invoke({
        "messages": [HumanMessage(content="Create a professional business proposal with custom branding")],
        "intent": None,
        "renderer": None,
        "document_spec": None,
        "pdf_path": None,
        "chat_response": None,
        "error": None
    })
    
    print(f"Selected renderer: {result.get('renderer')}")
    print(f"Output: {result.get('chat_response')}")
