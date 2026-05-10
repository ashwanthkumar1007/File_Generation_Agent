"""API routes for the File Generation Agent."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from pdf_agent import session_store

router = APIRouter(prefix="/api/v1/generate", tags=["generate"])


class ChatRequest(BaseModel):
    message: str
    thread_id: str


class ChatResponse(BaseModel):
    thread_id: str
    intent: str
    chat_response: str | None = None
    document_title: str | None = None
    document_category: str | None = None
    renderer: str | None = None
    pdf_filename: str | None = None
    pdf_view_url: str | None = None
    pdf_download_url: str | None = None
    error: str | None = None


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, request: Request):
    graph = request.app.state.graph
    state = session_store.get_or_create(body.thread_id)
    state["messages"] = [*state["messages"], HumanMessage(content=body.message)]

    try:
        result = graph.invoke(state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    updated = session_store.update(body.thread_id, result)
    intent = updated.get("intent", "")

    pdf_view_url = None
    pdf_download_url = None
    pdf_filename = None
    document_title = None

    if updated.get("pdf_path") and intent in ("create", "edit"):
        pdf_filename = os.path.basename(updated["pdf_path"])
        pdf_view_url = f"/api/v1/generate/view/{pdf_filename}"
        pdf_download_url = f"/api/v1/generate/download/{pdf_filename}"

    doc_spec = updated.get("document_spec")
    if doc_spec and isinstance(doc_spec, dict):
        document_title = doc_spec.get("title")

    return ChatResponse(
        thread_id=body.thread_id,
        intent=intent,
        chat_response=updated.get("chat_response"),
        document_title=document_title,
        document_category=updated.get("document_category"),
        renderer=updated.get("renderer"),
        pdf_filename=pdf_filename,
        pdf_view_url=pdf_view_url,
        pdf_download_url=pdf_download_url,
        error=updated.get("error"),
    )


@router.get("/view/{filename}")
async def view(filename: str, request: Request):
    """Serve the PDF inline so the browser renders it in a new tab."""
    config = request.app.state.agent_config
    safe_name = Path(filename).name
    file_path = Path(config.output_dir) / safe_name

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    suffix = file_path.suffix.lower()
    media_type = "text/markdown" if suffix == ".md" else "application/pdf"

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=safe_name,
        content_disposition_type="inline",
    )


@router.get("/download/{filename}")
async def download(filename: str, request: Request):
    """Serve the file as a download attachment."""
    config = request.app.state.agent_config
    safe_name = Path(filename).name
    file_path = Path(config.output_dir) / safe_name

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    suffix = file_path.suffix.lower()
    media_type = "text/markdown" if suffix == ".md" else "application/pdf"

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=safe_name,
        content_disposition_type="attachment",
    )


@router.get("/health")
async def health():
    return {"status": "ok"}
