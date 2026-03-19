"""Dynamic renderer selection node with extensible registry pattern.

This module selects the appropriate renderer based on user requirements using
an LLM-powered decision system. The architecture supports easy addition of
new renderers or file generation types through a centralized registry.

Architecture:
    - Registry pattern: Add new renderers by registering metadata
    - Dynamic prompt generation: Adapts to available renderers
    - Type-safe: Pydantic models for validation
    - Extensible: Supports PDF, Markdown, and future formats

Usage:
    # In graph definition
    from pdf_agent.nodes.select_renderer import select_renderer
    graph.add_node("select_renderer", lambda state: select_renderer(state, llm))

Adding a new renderer:
    RENDERER_REGISTRY["new_renderer"] = RendererMetadata(
        name="new_renderer",
        output_formats=["pdf"],
        use_cases=["specific use case"],
        best_for="when to use this renderer",
        capabilities=["feature1", "feature2"]
    )
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from pdf_agent.graph.state import PDFAgentState
from pdf_agent.utils.logger import get_logger

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Renderer Metadata Registry
# ═══════════════════════════════════════════════════════════════════════════


class RendererMetadata(BaseModel):
    """Metadata describing a renderer's capabilities and use cases."""

    name: str
    output_formats: list[str] = Field(
        description="File formats this renderer can produce (e.g., ['pdf', 'html'])"
    )
    use_cases: list[str] = Field(
        description="Common use cases or document types (e.g., ['invoices', 'reports'])"
    )
    best_for: str = Field(
        description="Human-readable description of when to use this renderer"
    )
    capabilities: list[str] = Field(
        default_factory=list,
        description="Technical capabilities (e.g., ['annotations', 'digital_signatures'])"
    )
    priority: int = Field(
        default=50,
        description="Selection priority (higher = preferred when ambiguous). Range: 0-100"
    )
    enabled: bool = Field(
        default=True,
        description="Whether this renderer is currently available"
    )


# Central registry of all available renderers
# Add new renderers here to make them available for selection
RENDERER_REGISTRY: dict[str, RendererMetadata] = {
    "fpdf2": RendererMetadata(
        name="fpdf2",
        output_formats=["pdf"],
        use_cases=[
            "invoices",
            "certificates",
            "forms",
            "receipts",
            "tickets",
            "labels",
            "simple_reports"
        ],
        best_for=(
            "Simple programmatic PDFs with templated layouts. Best for invoices, "
            "certificates, form-like documents, or when the user mentions a "
            "fixed/standard template. Fast and lightweight."
        ),
        capabilities=["text", "basic_tables", "images", "shapes", "templated_layouts"],
        priority=60,
    ),
    "weasyprint": RendererMetadata(
        name="weasyprint",
        output_formats=["pdf"],
        use_cases=[
            "reports",
            "proposals",
            "brochures",
            "newsletters",
            "branded_documents",
            "marketing_materials",
            "business_documents"
        ],
        best_for=(
            "Pixel-perfect, professionally designed documents rendered from HTML/CSS. "
            "Best for reports, proposals, branded documents, anything needing custom "
            "fonts, colors, complex layouts, headers, footers, or precise design control."
        ),
        capabilities=[
            "custom_fonts",
            "css_styling",
            "headers_footers",
            "page_numbers",
            "complex_layouts",
            "professional_design",
            "responsive_tables"
        ],
        priority=70,
    ),
    "borb": RendererMetadata(
        name="borb",
        output_formats=["pdf"],
        use_cases=[
            "contracts",
            "legal_documents",
            "interactive_forms",
            "technical_specifications",
            "annotated_documents"
        ],
        best_for=(
            "Complex documents with advanced PDF features — annotations, form fields, "
            "precise table control, digital signatures, PDF manipulation, or when "
            "programmatic control over PDF internals is needed."
        ),
        capabilities=[
            "annotations",
            "form_fields",
            "digital_signatures",
            "pdf_manipulation",
            "precise_table_control",
            "metadata",
            "encryption"
        ],
        priority=40,
        enabled=False,  # Disabled by default due to complexity and setup requirements
    ),
    "markdown": RendererMetadata(
        name="markdown",
        output_formats=["pdf", "md", "html"],
        use_cases=[
            "documentation",
            "readme_files",
            "technical_docs",
            "api_docs",
            "developer_docs",
            "changelog",
            "notes"
        ],
        best_for=(
            "Developer documentation, READMEs, technical documentation, or when "
            "the user explicitly wants Markdown/plain structured text output "
            "converted to PDF. Simple, readable, version-control friendly."
        ),
        capabilities=[
            "code_blocks",
            "syntax_highlighting",
            "simple_formatting",
            "portability",
            "plain_text"
        ],
        priority=50,
    ),
}


# ═══════════════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════════════


def get_enabled_renderers() -> dict[str, RendererMetadata]:
    """Return only enabled renderers from the registry."""
    return {name: meta for name, meta in RENDERER_REGISTRY.items() if meta.enabled}


def generate_renderer_prompt(user_request: str, available_renderers: dict[str, RendererMetadata]) -> str:
    """Generate a dynamic prompt based on available renderers.
    
    Args:
        user_request: The user's original request
        available_renderers: Dictionary of enabled renderer metadata
        
    Returns:
        Formatted prompt string for the LLM
    """
    # Sort by priority (high to low) for better presentation
    sorted_renderers = sorted(
        available_renderers.items(),
        key=lambda x: x[1].priority,
        reverse=True
    )
    
    renderer_descriptions = []
    for name, meta in sorted_renderers:
        desc = f"- **{name}**: {meta.best_for}"
        if meta.use_cases:
            use_cases_str = ", ".join(meta.use_cases[:5])  # Limit for prompt clarity
            desc += f"\n  Common use cases: {use_cases_str}"
        renderer_descriptions.append(desc)
    
    prompt = f"""You are deciding which renderer to use for document generation based on the user's request.

Available renderers:

{chr(10).join(renderer_descriptions)}

User request: {user_request}

Analyze the request and pick the single best renderer. Consider:
1. Document type and purpose
2. Required features and capabilities
3. Design complexity and layout needs
4. Technical requirements (forms, signatures, etc.)

Provide clear reasoning for your choice.
"""
    return prompt


def get_valid_renderer_names() -> list[str]:
    """Return list of enabled renderer names for Pydantic validation."""
    return list(get_enabled_renderers().keys())


# ═══════════════════════════════════════════════════════════════════════════
# Pydantic Models
# ═══════════════════════════════════════════════════════════════════════════


class RendererSelection(BaseModel):
    """LLM output model for renderer selection decision."""
    
    renderer: str = Field(
        description="The selected renderer name from available options"
    )
    reasoning: str = Field(
        description="Explanation of why this renderer was chosen (useful for debugging)"
    )
    confidence: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Confidence score for this selection (0.0 to 1.0)"
    )
    alternative: str | None = Field(
        default=None,
        description="Alternative renderer if confidence is low"
    )
    
    def validate_renderer(self, valid_renderers: set[str]) -> None:
        """Validate that selected renderer exists in registry."""
        if self.renderer not in valid_renderers:
            raise ValueError(
                f"Selected renderer '{self.renderer}' not found in registry. "
                f"Available: {', '.join(sorted(valid_renderers))}"
            )


# ═══════════════════════════════════════════════════════════════════════════
# Main Node Function
# ═══════════════════════════════════════════════════════════════════════════


def select_renderer(state: PDFAgentState, *, llm: Any) -> dict[str, Any]:
    """Select the appropriate renderer based on user request using LLM.
    
    This node analyzes the user's request and selects the best renderer from
    the available registry. On edit turns, it preserves the existing renderer
    to maintain consistency.
    
    Args:
        state: Current PDFAgentState containing messages and intent
        llm: Language model instance for making selection decisions
        
    Returns:
        State update dict with selected renderer, or empty dict if no change needed
        
    Behavior:
        - On "edit" intent: Preserves existing renderer (no re-selection)
        - On initial/generate intent: Selects optimal renderer via LLM
        - Validates selection against registry
        - Logs selection with reasoning for debugging
        
    Raises:
        ValueError: If LLM selects a renderer not in the registry
        RuntimeError: If no renderers are enabled in the registry
        
    State updates:
        - renderer: str - The selected renderer name
        - renderer_metadata: dict - Renderer capabilities and info (optional)
    """
    logger.info("Entering renderer selection node")
    
    # ─── Preserve renderer on edit turns ─────────────────────────────────
    if state.get("renderer") and state.get("intent") == "edit":
        logger.info(
            f"Edit intent detected - preserving existing renderer: {state['renderer']}"
        )
        return {}  # No state change needed
    
    # ─── Get available renderers ──────────────────────────────────────────
    available_renderers = get_enabled_renderers()
    
    if not available_renderers:
        logger.error("No renderers are enabled in the registry")
        raise RuntimeError(
            "Renderer registry is empty or all renderers are disabled. "
            "Check RENDERER_REGISTRY configuration."
        )
    
    logger.info(
        f"Available renderers: {', '.join(available_renderers.keys())} "
        f"(total: {len(available_renderers)})"
    )
    
    # ─── Extract user request ──────────────────────────────────────────────
    user_request = str(state["messages"][-1])
    logger.debug(f"User request: {user_request[:100]}...")
    
    # ─── Generate dynamic prompt ───────────────────────────────────────────
    prompt = generate_renderer_prompt(user_request, available_renderers)
    
    # ─── Invoke LLM for selection ──────────────────────────────────────────
    logger.info("Invoking LLM for renderer selection")
    try:
        structured_llm = llm.with_structured_output(RendererSelection)
        result: RendererSelection = structured_llm.invoke(prompt)
        
        # Validate selection
        result.validate_renderer(set(available_renderers.keys()))
        
        logger.info(
            f"Renderer selected: {result.renderer} "
            f"(confidence: {result.confidence:.2f})"
        )
        logger.debug(f"Selection reasoning: {result.reasoning}")
        
        if result.alternative:
            logger.debug(f"Alternative renderer suggested: {result.alternative}")
        
        # ─── Prepare state update ──────────────────────────────────────────
        state_update = {
            "renderer": result.renderer,
            # Optional: Include metadata for downstream nodes
            # "renderer_metadata": available_renderers[result.renderer].model_dump()
        }
        
        return state_update
        
    except Exception as e:
        logger.error(f"Renderer selection failed: {e}", exc_info=True)
        # Fallback to highest priority renderer
        fallback = max(available_renderers.items(), key=lambda x: x[1].priority)[0]
        logger.warning(f"Falling back to highest priority renderer: {fallback}")
        
        return {
            "renderer": fallback,
            "error": f"Renderer selection failed, using fallback: {fallback}"
        }


# ═══════════════════════════════════════════════════════════════════════════
# Utility Functions for External Use
# ═══════════════════════════════════════════════════════════════════════════


def register_renderer(metadata: RendererMetadata) -> None:
    """Register a new renderer at runtime.
    
    Args:
        metadata: RendererMetadata instance describing the new renderer
        
    Example:
        >>> register_renderer(RendererMetadata(
        ...     name="custom_pdf_lib",
        ...     output_formats=["pdf"],
        ...     use_cases=["custom_layouts"],
        ...     best_for="Specialized custom layouts"
        ... ))
    """
    if metadata.name in RENDERER_REGISTRY:
        logger.warning(f"Overwriting existing renderer: {metadata.name}")
    
    RENDERER_REGISTRY[metadata.name] = metadata
    logger.info(f"Registered renderer: {metadata.name}")


def disable_renderer(renderer_name: str) -> None:
    """Disable a renderer without removing it from registry.
    
    Args:
        renderer_name: Name of the renderer to disable
    """
    if renderer_name in RENDERER_REGISTRY:
        RENDERER_REGISTRY[renderer_name].enabled = False
        logger.info(f"Disabled renderer: {renderer_name}")
    else:
        logger.warning(f"Cannot disable unknown renderer: {renderer_name}")


def enable_renderer(renderer_name: str) -> None:
    """Enable a previously disabled renderer.
    
    Args:
        renderer_name: Name of the renderer to enable
    """
    if renderer_name in RENDERER_REGISTRY:
        RENDERER_REGISTRY[renderer_name].enabled = True
        logger.info(f"Enabled renderer: {renderer_name}")
    else:
        logger.warning(f"Cannot enable unknown renderer: {renderer_name}")


def list_renderers(enabled_only: bool = False) -> dict[str, RendererMetadata]:
    """List all renderers with their metadata.
    
    Args:
        enabled_only: If True, return only enabled renderers
        
    Returns:
        Dictionary mapping renderer names to their metadata
    """
    if enabled_only:
        return get_enabled_renderers()
    return RENDERER_REGISTRY.copy()
