## PDF Generation Agent

A conversational AI agent that generates and edits professional PDF reports from natural language prompts.

Built with LangGraph for agentic orchestration, the system follows a strict separation of concerns:
the LLM never produces HTML or PDFs directly — it only generates and edits a structured `DocumentSpec`
(JSON schema), which is then rendered into a PDF entirely in Python via Jinja2 templates and WeasyPrint.

### Features

- 🧠 Intent classification — automatically detects create, edit, or chat requests
- 📄 Structured document generation — headings, paragraphs, bullet lists, tables, and charts
- ✏️ Iterative editing — refine any part of the document through follow-up prompts
- 📊 Chart rendering — matplotlib-powered bar, line, pie, and scatter charts embedded as images
- 💬 General chat — answers questions without triggering PDF generation
- 🔌 Multi-provider LLM support — Azure AI Foundry, OpenAI, Anthropic Claude, Google Gemini, AWS Bedrock

### Stack

LangGraph · LangChain · Pydantic · WeasyPrint · Jinja2 · Matplotlib
