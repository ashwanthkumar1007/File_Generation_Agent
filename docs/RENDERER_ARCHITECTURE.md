# Renderer Selection Architecture

## Overview

The renderer selection system uses a **registry pattern** with **LLM-powered decision making** to dynamically choose the best renderer for document generation. This architecture is designed for extensibility, making it easy to add new renderers or support additional file formats.

## Architecture Principles

### 1. Registry Pattern

All renderers are registered in a central `RENDERER_REGISTRY` with comprehensive metadata:

- **Capabilities**: What the renderer can do
- **Use cases**: When to use it
- **Output formats**: What file types it produces
- **Priority**: Selection preference when ambiguous

### 2. Dynamic Prompt Generation

Instead of hardcoded prompts, the system automatically generates selection prompts based on available renderers in the registry. This means:

- Adding a new renderer automatically updates the LLM prompt
- Disabling a renderer removes it from consideration
- No manual prompt maintenance required

### 3. Type Safety

Pydantic models ensure:

- Renderer metadata is validated at registration
- LLM output is structured and validated
- State transitions are type-safe

### 4. Separation of Concerns

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   User      │────▶│   select_    │────▶│  Specific   │
│   Request   │     │   renderer   │     │  Renderer   │
└─────────────┘     └──────────────┘     └─────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │  LLM makes   │
                    │  decision    │
                    └──────────────┘
```

## Core Components

### 1. RendererMetadata

Describes a renderer's capabilities:

```python
class RendererMetadata(BaseModel):
    name: str                    # Unique identifier
    output_formats: list[str]    # ["pdf", "html", "md"]
    use_cases: list[str]         # ["reports", "invoices"]
    best_for: str                # Human description
    capabilities: list[str]      # ["annotations", "forms"]
    priority: int                # 0-100, higher = preferred
    enabled: bool                # Runtime toggle
```

### 2. RENDERER_REGISTRY

Central dictionary mapping renderer names to metadata:

```python
RENDERER_REGISTRY = {
    "weasyprint": RendererMetadata(...),
    "fpdf2": RendererMetadata(...),
    "borb": RendererMetadata(...),
    "markdown": RendererMetadata(...),
}
```

### 3. select_renderer() Node

Main LangGraph node that:

1. Checks if renderer already selected (edit mode preservation)
2. Gets enabled renderers from registry
3. Generates dynamic prompt
4. Invokes LLM with structured output
5. Validates and returns selection

## Adding a New Renderer

### Step 1: Implement the Renderer

Create your renderer implementation (e.g., `pdf_agent/rendering/new_renderer.py`):

```python
"""My custom renderer implementation."""
from pathlib import Path

def render_with_custom_lib(document_spec: dict, output_path: Path) -> Path:
    """Render document using custom library."""
    # Your rendering logic here
    return output_path
```

### Step 2: Register the Renderer

Add to `RENDERER_REGISTRY` in `nodes/select_renderer.py`:

```python
RENDERER_REGISTRY["custom_lib"] = RendererMetadata(
    name="custom_lib",
    output_formats=["pdf"],
    use_cases=[
        "specialized_layouts",
        "custom_branding",
        "specific_industry_docs"
    ],
    best_for=(
        "Documents requiring specialized layouts and custom branding "
        "specific to [your industry/use case]."
    ),
    capabilities=[
        "custom_feature_1",
        "custom_feature_2",
        "advanced_layouts"
    ],
    priority=55,  # Between markdown (50) and fpdf2 (60)
    enabled=True
)
```

### Step 3: Add Rendering Logic

Update the rendering router (e.g., in your graph or a render dispatch function):

```python
def dispatch_renderer(state: PDFAgentState) -> PDFAgentState:
    """Route to appropriate renderer based on selection."""
    renderer = state["renderer"]

    if renderer == "custom_lib":
        from pdf_agent.rendering.new_renderer import render_with_custom_lib
        output_path = render_with_custom_lib(
            state["document_spec"],
            Path("output/document.pdf")
        )
        return {"pdf_path": str(output_path)}

    elif renderer == "weasyprint":
        # Existing weasyprint logic
        ...
    # ... other renderers
```

### Step 4: Test

```python
# Test renderer selection
result = select_renderer(
    state={
        "messages": ["Create a specialized industry document"],
        "intent": "generate"
    },
    llm=your_llm_instance
)

assert result["renderer"] == "custom_lib"
```

## Adding Support for New File Formats

### Example: Excel Spreadsheet Generation

#### 1. Create the Renderer

```python
# pdf_agent/rendering/excel_renderer.py
import openpyxl
from pathlib import Path

def render_to_excel(document_spec: dict, output_path: Path) -> Path:
    """Render document spec to Excel spreadsheet."""
    wb = openpyxl.Workbook()
    ws = wb.active

    # Transform document_spec to Excel format
    for idx, section in enumerate(document_spec.get("sections", [])):
        ws.cell(row=idx+1, column=1, value=section["heading"])
        # ... more rendering logic

    wb.save(output_path)
    return output_path
```

#### 2. Register the Renderer

```python
RENDERER_REGISTRY["excel"] = RendererMetadata(
    name="excel",
    output_formats=["xlsx", "xls"],
    use_cases=[
        "financial_reports",
        "data_tables",
        "spreadsheet_analysis",
        "budgets",
        "datasets"
    ],
    best_for=(
        "Tabular data, financial reports, datasets, or any content "
        "that benefits from spreadsheet format with rows, columns, "
        "and Excel formulas."
    ),
    capabilities=[
        "formulas",
        "multiple_sheets",
        "cell_formatting",
        "charts",
        "pivot_tables"
    ],
    priority=45,
    enabled=True
)
```

#### 3. Update State (if needed)

```python
# In pdf_agent/graph/state.py
class PDFAgentState(TypedDict):
    messages: list[BaseMessage]
    intent: str
    renderer: str | None
    # Generic output path instead of pdf-specific
    output_path: str | None  # Changed from pdf_path
    output_format: str | None  # Add format field
    # ... other fields
```

## Runtime Configuration

### Disable a Renderer

```python
from pdf_agent.nodes.select_renderer import disable_renderer

disable_renderer("borb")  # Temporarily unavailable
```

### Enable a Renderer

```python
from pdf_agent.nodes.select_renderer import enable_renderer

enable_renderer("borb")
```

### List Available Renderers

```python
from pdf_agent.nodes.select_renderer import list_renderers

all_renderers = list_renderers(enabled_only=False)
active_renderers = list_renderers(enabled_only=True)

for name, meta in active_renderers.items():
    print(f"{name}: {meta.best_for}")
```

### Dynamic Registration

```python
from pdf_agent.nodes.select_renderer import register_renderer, RendererMetadata

# Register at runtime (e.g., from plugin or config)
register_renderer(RendererMetadata(
    name="plugin_renderer",
    output_formats=["pdf"],
    use_cases=["plugin_specific"],
    best_for="Dynamically loaded plugin renderer"
))
```

## Advanced: Multi-Format Support

### Supporting Multiple Output Formats from One Renderer

```python
RENDERER_REGISTRY["pandoc"] = RendererMetadata(
    name="pandoc",
    output_formats=["pdf", "docx", "html", "epub"],
    use_cases=[
        "multi_format_docs",
        "ebook_generation",
        "format_conversion"
    ],
    best_for=(
        "Documents that need to be exported in multiple formats "
        "(PDF, Word, HTML, ePub) from the same source."
    ),
    capabilities=[
        "markdown_input",
        "format_conversion",
        "citations",
        "cross_references"
    ],
    priority=40,
    enabled=True
)
```

Then handle format selection in your render logic:

```python
def dispatch_renderer(state: PDFAgentState) -> PDFAgentState:
    renderer = state["renderer"]
    desired_format = state.get("output_format", "pdf")

    if renderer == "pandoc":
        output = render_with_pandoc(
            state["document_spec"],
            output_format=desired_format
        )
        return {"output_path": str(output), "output_format": desired_format}
```

## Debugging

### Enable Debug Logging

```python
from pdf_agent.utils.logger import setup_logging
import logging

setup_logging(level=logging.DEBUG)
```

### View Selection Reasoning

The `RendererSelection` model includes a `reasoning` field:

```python
# In your logs, you'll see:
# INFO | ... | Selection reasoning: User requested a branded business
# proposal with custom fonts and colors, which aligns best with
# weasyprint's HTML/CSS rendering capabilities.
```

### Inspect Renderer Metadata

```python
from pdf_agent.nodes.select_renderer import RENDERER_REGISTRY

for name, meta in RENDERER_REGISTRY.items():
    print(f"\n{name}:")
    print(f"  Priority: {meta.priority}")
    print(f"  Capabilities: {', '.join(meta.capabilities)}")
    print(f"  Enabled: {meta.enabled}")
```

## Best Practices

### 1. Clear Use Case Descriptions

Make `use_cases` and `best_for` specific and distinguishable:

- ✅ Good: "Financial invoices with line items and tax calculations"
- ❌ Bad: "Documents" (too vague)

### 2. Appropriate Priority Values

- 90-100: Specialized, high-value renderers
- 70-89: General-purpose, reliable choices
- 50-69: Good for specific use cases
- 30-49: Niche or specialized
- 0-29: Fallback or experimental

### 3. Comprehensive Capabilities

List technical capabilities to help debugging:

```python
capabilities=[
    "pdf_a_compliance",      # Specific standards
    "accessibility_tags",    # WCAG compliance
    "vector_graphics",       # Quality features
    "batch_processing"       # Performance features
]
```

### 4. Test Renderer Selection

Create test cases for ambiguous requests:

```python
def test_invoice_selection():
    result = select_renderer(
        state={"messages": ["Create an invoice"], "intent": "generate"},
        llm=mock_llm
    )
    assert result["renderer"] == "fpdf2"

def test_branded_report_selection():
    result = select_renderer(
        state={"messages": ["branded business proposal"], "intent": "generate"},
        llm=mock_llm
    )
    assert result["renderer"] == "weasyprint"
```

## Future Extensions

### Conditional Renderer Availability

```python
class RendererMetadata(BaseModel):
    # ... existing fields ...
    requires_packages: list[str] = []  # ["weasyprint>=60.0"]
    min_python_version: str = "3.10"
    platform_support: list[str] = ["linux", "macos", "windows"]

    def is_available(self) -> bool:
        """Check if renderer can be used in current environment."""
        # Check package availability, Python version, platform
        return all_requirements_met()
```

### Renderer Performance Metrics

```python
class RendererMetadata(BaseModel):
    # ... existing fields ...
    avg_render_time_ms: int | None = None
    memory_usage_mb: int | None = None
    max_page_count: int | None = None
```

### Cost-Based Selection

```python
class RendererMetadata(BaseModel):
    # ... existing fields ...
    cost_per_page: float = 0.0  # For cloud/API-based renderers
    api_rate_limit: int | None = None
```

## Conclusion

This architecture provides:

- ✅ **Extensibility**: Add renderers by updating registry only
- ✅ **Maintainability**: Centralized configuration, no scattered logic
- ✅ **Flexibility**: Runtime enable/disable, dynamic registration
- ✅ **Type Safety**: Pydantic validation throughout
- ✅ **Debuggability**: Clear logging and reasoning traces
- ✅ **Future-Proof**: Supports new formats, features, and requirements

When you need to add new renderers, file formats, or capabilities, you only touch the registry—the rest of the system adapts automatically.
