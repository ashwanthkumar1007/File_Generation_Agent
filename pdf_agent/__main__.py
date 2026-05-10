"""Allow running the package with ``python -m pdf_agent``."""

import uvicorn

uvicorn.run("pdf_agent.main:app", host="0.0.0.0", port=8001, reload=True)
