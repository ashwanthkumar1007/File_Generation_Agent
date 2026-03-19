# PDF Agent Flow Architecture

## Current Flow (Implemented)

```
┌─────────────────┐
│  User Message   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ classify_intent │  ← Detects: create | edit | chat
└────────┬────────┘
         │
    ┌────┼─────────────┐
    │                  │
    ▼                  ▼
┌─────────────┐  ┌──────────────┐
│select_      │  │ chat_        │
│renderer     │  │ response     │
└─────┬───────┘  └──────┬───────┘
      │                 │
      │                 ▼
      │               [END]
      ▼
┌─────────────────┐
│ generate_       │  ← Aware of selected renderer
│ content         │     (weasyprint|fpdf2|borb|markdown)
└────────┬────────┘
         │
    ┌────┼──────────┐
    │               │
    ▼               ▼
┌─────────┐   ┌──────────┐
│render   │   │apply_    │  ← If editing existing doc
│pdf      │   │edit      │
│(weasy   │   └────┬─────┘
│print)   │        │
└────┬────┘        │
     │             ▼
     │        ┌─────────┐
     │        │render   │
     │        │pdf      │
     │        └────┬────┘
     │             │
     └─────────────┘
           │
           ▼
         [END]
```

## Future Flow (Multi-Renderer Support)

When renderer-specific nodes are implemented:

```
┌─────────────────┐
│  User Message   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ classify_intent │
└────────┬────────┘
         │
    ┌────┼─────────────┐
    │                  │
    ▼                  ▼
┌─────────────┐  ┌──────────────┐
│select_      │  │ chat_        │
│renderer     │  │ response     │
│             │  └──────┬───────┘
│ Chooses:    │         │
│ • weasyprint│         ▼
│ • fpdf2     │       [END]
│ • borb      │
│ • markdown  │
└─────┬───────┘
      │
      ▼
┌─────────────────┐
│ generate_       │
│ content         │
└────────┬────────┘
         │
    ┌────┼────────────┬─────────────┬──────────────┐
    │                 │             │              │
    ▼                 ▼             ▼              ▼
┌─────────┐    ┌──────────┐  ┌──────────┐  ┌────────────┐
│render_  │    │render_   │  │render_   │  │render_     │
│pdf      │    │fpdf2     │  │borb      │  │markdown    │
│(weasy)  │    │          │  │          │  │            │
└────┬────┘    └─────┬────┘  └─────┬────┘  └──────┬─────┘
     │               │             │              │
     └───────────────┴─────────────┴──────────────┘
                          │
                          ▼
                        [END]

Note: For edit operations, flow goes through apply_edit first,
      then routes to appropriate renderer.
```

## Renderer Selection Logic

The `select_renderer` node uses an LLM with structured output to choose the optimal renderer:

```python
User Request: "Create an invoice for $500"
    ↓
LLM Analysis:
    - Document type: Invoice (simple, templated)
    - Features needed: Basic text, tables, fixed layout
    - Design complexity: Low
    ↓
Selected: fpdf2 (priority: 60)
Reasoning: "Invoice is a simple, form-like document best
            suited for programmatic generation with fpdf2"
```

```python
User Request: "Create a branded business proposal with custom fonts"
    ↓
LLM Analysis:
    - Document type: Business proposal (professional)
    - Features needed: Custom fonts, complex layout, branding
    - Design complexity: High
    ↓
Selected: weasyprint (priority: 70)
Reasoning: "Professional document requiring custom fonts and
            precise layout control, ideal for HTML/CSS rendering"
```

## Routing Functions

### 1. \_route_by_intent

Routes after intent classification:

- `create` → `select_renderer`
- `edit` → `select_renderer` (preserves existing renderer)
- `chat` → `chat_response`

### 2. \_route_after_generate

Routes after content generation:

- If `intent == "edit"` → `apply_edit` (then to renderer)
- Otherwise → `render_pdf` (or specific renderer node)

### 3. \_route_by_renderer (Future)

Routes to specific renderer implementation:

- `"weasyprint"` → `render_pdf`
- `"fpdf2"` → `render_fpdf2`
- `"borb"` → `render_borb`
- `"markdown"` → `render_markdown`

## State Flow

The `PDFAgentState` carries information through the graph:

```python
{
    "messages": [...],           # Conversation history
    "intent": "create",          # From classify_intent
    "renderer": "weasyprint",    # From select_renderer
    "document_spec": {...},      # From generate_content or apply_edit
    "pdf_path": "/path/to.pdf",  # From render node
    "chat_response": "...",      # From chat_response
    "error": None                # Any error messages
}
```

## Key Design Principles

1. **Separation of Concerns**
   - LLM only makes decisions and generates structured content
   - Python does all rendering (no LLM-generated HTML/PDF)

2. **Renderer Awareness**
   - Content generation is aware of selected renderer
   - Can adjust document structure based on renderer capabilities

3. **Extensibility**
   - New renderers added via registry pattern
   - Routing logic automatically adapts
   - No changes to existing nodes required

4. **Edit Consistency**
   - Edit operations preserve original renderer
   - Ensures consistent output across iterations

## Adding a New Renderer

To add a new renderer (e.g., "reportlab"):

1. **Register in select_renderer.py:**

   ```python
   RENDERER_REGISTRY["reportlab"] = RendererMetadata(
       name="reportlab",
       output_formats=["pdf"],
       use_cases=["technical_diagrams", "flowcharts"],
       best_for="Documents with programmatic diagrams",
       priority=55
   )
   ```

2. **Create node file:**

   ```python
   # pdf_agent/nodes/render_reportlab.py
   def render_reportlab(state, *, config):
       # Implementation
       return {"pdf_path": output_path}
   ```

3. **Register in graph:**

   ```python
   # pdf_agent/graph/pdf_agent_graph.py
   graph.add_node("render_reportlab",
                  partial(render_reportlab, config=config))
   ```

4. **Update routing:**
   ```python
   renderer_node_map = {
       ...
       "reportlab": "render_reportlab",  # Add this line
   }
   ```

That's it! The LLM will now consider and route to your new renderer.
