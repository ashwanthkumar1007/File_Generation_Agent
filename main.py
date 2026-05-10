"""Root entry point — starts the FastAPI server."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("pdf_agent.main:app", host="0.0.0.0", port=8001, reload=True)
