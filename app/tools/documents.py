"""Center document library: lets the agent save a generated document (HTML or
Markdown) as part of its reply, instead of only replying with chat text.

The tool is bound to the chat session/user it's running in via a factory
(``make_save_document_tool``) so each request gets a fresh closure - the SDK
tool signature itself has no access to FastAPI's request context.
"""

import json
import time
import uuid
from pathlib import Path
from typing import Annotated, Any

from claude_agent_sdk import tool

from app.db import SessionLocal
from app.models import Document

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DOCUMENTS_DIR = PROJECT_ROOT / "workspace" / "documents"

DOC_EXTENSIONS = {"html": "html", "markdown": "md"}


def _safe_title(title: str) -> str:
    title = title.strip() or "Untitled document"
    return title[:255]


def make_save_document_tool(session_id: int | None, user_id: int | None):
    @tool(
        "save_document",
        "Save a generated document (HTML or Markdown) to the center document "
        "library, so it appears as a document in your reply instead of raw text "
        "dumped into chat. Use this for reports, summaries, tables, or any content "
        "worth keeping and revisiting later - not for short conversational answers. "
        "Use doc_type 'markdown' for anything that's mainly a table or list (invoice "
        "listings, per-agent breakdowns, etc.), even a large one with dozens of rows "
        "- it's rendered as a real formatted table, and a plain markdown table is far "
        "less likely to have a JSON-escaping mistake than a large HTML string full of "
        "quoted attributes. Only use 'html' for documents that need custom visual "
        "layout beyond a table. After saving, briefly mention in your normal reply "
        "that you created the document; do not repeat its full content in chat.",
        {
            "title": Annotated[str, "Short, human-readable title for the document."],
            "content": Annotated[str, "The full document content (HTML or Markdown)."],
            "doc_type": Annotated[str, "Either 'html' or 'markdown' - prefer 'markdown' for tables/lists."],
        },
    )
    async def save_document(args: dict[str, Any]) -> dict[str, Any]:
        # DEBUG(temp): tracing a stall that happens right around report
        # generation - this proves whether the tool handler itself (file
        # write / DB commit) is what hangs, vs. the model never finishing the
        # call. Remove once resolved (search "DEBUG(temp)").
        t0 = time.monotonic()
        title = _safe_title(str(args.get("title", "")))
        content = args.get("content", "")
        doc_type = str(args.get("doc_type", "html")).lower()
        print(f"[save_document-debug] enter title={title!r} doc_type={doc_type} content_len={len(content)}", flush=True)
        if doc_type not in DOC_EXTENSIONS:
            return {
                "content": [{"type": "text", "text": "doc_type must be 'html' or 'markdown'."}],
                "is_error": True,
            }
        if not content or not content.strip():
            return {
                "content": [{"type": "text", "text": "Document content is empty."}],
                "is_error": True,
            }

        DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
        ext = DOC_EXTENSIONS[doc_type]
        stored_name = f"{uuid.uuid4().hex}.{ext}"
        (DOCUMENTS_DIR / stored_name).write_text(content, encoding="utf-8")
        print(f"[save_document-debug] +{time.monotonic() - t0:.1f}s file written", flush=True)

        async with SessionLocal() as db:
            doc = Document(
                session_id=session_id,
                user_id=user_id,
                title=title,
                doc_type=doc_type,
                filename=stored_name,
            )
            db.add(doc)
            await db.commit()
            await db.refresh(doc)
            doc_id = doc.id
        print(f"[save_document-debug] +{time.monotonic() - t0:.1f}s db committed doc_id={doc_id}", flush=True)

        marker = json.dumps({"document_id": doc_id, "title": title, "doc_type": doc_type})
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"{marker}\n"
                        f"Document saved to the library as #{doc_id}. Tell the user it's ready; "
                        "don't repeat the full content in chat."
                    ),
                }
            ]
        }

    return save_document
