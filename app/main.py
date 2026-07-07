import asyncio
import json
import re
import time
import uuid
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    StreamEvent,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    query,
)
from fastapi import Depends, FastAPI, File, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import (
    AVAILABLE_EFFORT_LEVELS,
    AVAILABLE_MODELS,
    DEFAULT_EFFORT,
    build_options,
)
from app.config import settings
from app.pricing import estimate_cost_usd
from app.auth import (
    SESSION_COOKIE,
    SESSION_MAX_AGE_SECONDS,
    get_current_user,
    make_session_cookie,
    verify_password,
)
from app.db import SessionLocal, get_session
from app.models import ChatMessage, ChatSession, Document, User
from app.settings_store import (
    KNOWN_KEYS,
    get_settings,
    list_settings_status,
    set_setting,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOADS_DIR = PROJECT_ROOT / "workspace" / "uploads"
DOCUMENTS_DIR = PROJECT_ROOT / "workspace" / "documents"

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB per file
PING_INTERVAL_SECONDS = 15  # keepalive cadence while the model is silently generating

app = FastAPI(title="EE Finance Agent")


def _safe_filename(name: str) -> str:
    name = Path(name).name  # strip any directory components
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip() or "file"
    return name


class LoginRequest(BaseModel):
    username: str
    password: str


VALID_MODES = {"discussion", "builder"}


class NewSessionRequest(BaseModel):
    title: str | None = None
    mode: str = "discussion"


class Attachment(BaseModel):
    filename: str
    path: str  # project-relative path, e.g. workspace/uploads/3/abc123_report.pdf


class NewMessageRequest(BaseModel):
    content: str
    model: str | None = None
    effort: str | None = None
    attachments: list[Attachment] | None = None


@app.get("/api/chat/options")
async def chat_options(user: User = Depends(get_current_user)):
    return {
        "models": [{"id": k, "label": v} for k, v in AVAILABLE_MODELS.items()],
        "default_model": settings.finance_agent_model,
        "effort_levels": AVAILABLE_EFFORT_LEVELS,
        "default_effort": DEFAULT_EFFORT,
    }


@app.post("/api/login")
async def login(body: LoginRequest, response: Response, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    token = make_session_cookie(user.id)
    response.set_cookie(
        SESSION_COOKIE, token, max_age=SESSION_MAX_AGE_SECONDS, httponly=True, samesite="lax"
    )
    return {"id": user.id, "username": user.username, "role": user.role}


@app.post("/api/logout")
async def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@app.get("/api/me")
async def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "username": user.username, "role": user.role}


class UpdateSettingsRequest(BaseModel):
    settings: dict[str, str | None]


@app.get("/api/settings")
async def get_app_settings(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    return await list_settings_status(session)


@app.put("/api/settings")
async def update_app_settings(
    body: UpdateSettingsRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    unknown = set(body.settings) - KNOWN_KEYS
    if unknown:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Unknown setting key(s): {', '.join(sorted(unknown))}"
        )
    for key, value in body.settings.items():
        await set_setting(session, key, value)
    return await list_settings_status(session)


@app.get("/api/chat/sessions")
async def list_sessions(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(ChatSession).where(ChatSession.user_id == user.id).order_by(ChatSession.id.desc())
    )
    sessions = result.scalars().all()
    return [
        {"id": s.id, "title": s.title, "mode": s.mode, "created_at": s.created_at}
        for s in sessions
    ]


@app.post("/api/chat/sessions")
async def create_session(
    body: NewSessionRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    mode = body.mode if body.mode in VALID_MODES else "discussion"
    chat_session = ChatSession(user_id=user.id, title=body.title, mode=mode)
    session.add(chat_session)
    await session.commit()
    await session.refresh(chat_session)
    return {
        "id": chat_session.id,
        "title": chat_session.title,
        "mode": chat_session.mode,
        "created_at": chat_session.created_at,
    }


@app.get("/api/chat/sessions/{session_id}/messages")
async def get_messages(
    session_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    chat_session = await session.get(ChatSession, session_id)
    if chat_session is None or chat_session.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    messages = await _get_history(session, session_id)
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "attachments": json.loads(m.attachments) if m.attachments else [],
            "created_at": m.created_at,
        }
        for m in messages
    ]


@app.get("/api/chat/sessions/{session_id}/usage")
async def get_session_usage(
    session_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    chat_session = await session.get(ChatSession, session_id)
    if chat_session is None or chat_session.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")

    result = await session.execute(
        select(
            func.coalesce(func.sum(ChatMessage.input_tokens), 0),
            func.coalesce(func.sum(ChatMessage.output_tokens), 0),
            func.coalesce(func.sum(ChatMessage.cache_creation_input_tokens), 0),
            func.coalesce(func.sum(ChatMessage.cache_read_input_tokens), 0),
            func.coalesce(func.sum(ChatMessage.cost_usd), 0),
            func.count(ChatMessage.id),
        ).where(ChatMessage.session_id == session_id, ChatMessage.role == "assistant")
    )
    input_tokens, output_tokens, cache_write, cache_read, cost_usd, turns = result.one()
    return {
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
        "cache_creation_input_tokens": int(cache_write),
        "cache_read_input_tokens": int(cache_read),
        "cost_usd": float(cost_usd),
        "turns": int(turns),
    }


@app.post("/api/chat/sessions/{session_id}/upload")
async def upload_file(
    session_id: int,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    chat_session = await session.get(ChatSession, session_id)
    if chat_session is None or chat_session.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")

    session_dir = UPLOADS_DIR / str(session_id)
    session_dir.mkdir(parents=True, exist_ok=True)

    safe_name = _safe_filename(file.filename or "file")
    stored_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
    dest = session_dir / stored_name

    size = 0
    with open(dest, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File too large (max 20MB)")
            out.write(chunk)

    rel_path = dest.relative_to(PROJECT_ROOT).as_posix()
    return {"filename": safe_name, "path": rel_path, "size": size}


@app.get("/api/chat/sessions/{session_id}/files/{stored_name}")
async def get_uploaded_file(
    session_id: int,
    stored_name: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    chat_session = await session.get(ChatSession, session_id)
    if chat_session is None or chat_session.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")

    safe_name = Path(stored_name).name  # prevent path traversal
    file_path = UPLOADS_DIR / str(session_id) / safe_name
    if not file_path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    return FileResponse(str(file_path))


@app.get("/api/documents")
async def list_documents(
    session_id: int | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Center document library. With no session_id, lists every document ever
    generated; pass session_id to see only what a given chat session produced."""
    stmt = select(Document).order_by(Document.id.desc())
    if session_id is not None:
        stmt = stmt.where(Document.session_id == session_id)
    result = await session.execute(stmt)
    docs = result.scalars().all()
    return [
        {
            "id": d.id,
            "session_id": d.session_id,
            "title": d.title,
            "doc_type": d.doc_type,
            "created_at": d.created_at,
        }
        for d in docs
    ]


@app.get("/api/documents/{doc_id}/content")
async def get_document_content(
    doc_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    doc = await session.get(Document, doc_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    file_path = DOCUMENTS_DIR / doc.filename
    if not file_path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document file missing")
    text = file_path.read_text(encoding="utf-8")
    if doc.doc_type == "html":
        return HTMLResponse(text)
    return PlainTextResponse(text, media_type="text/markdown")


TOOL_START_SUMMARIES = {
    "Bash": "Running a command…",
    "Write": "Writing a file…",
    "Edit": "Editing a file…",
    "Read": "Reading a file…",
    "Glob": "Searching files…",
}


def _tool_start_summary(name: str) -> str:
    """A generic label shown the instant a tool call starts generating - before
    its arguments (which _tool_summary describes) have streamed in. A tool's
    input can be large (e.g. save_document writing a full report), and no
    delta events are emitted while it's generated, so without this the UI
    shows no activity at all for that whole stretch."""
    if name in TOOL_START_SUMMARIES:
        return TOOL_START_SUMMARIES[name]
    if name.endswith("query_finance_db"):
        return "Querying the database…"
    if name.endswith("save_document"):
        return "Writing a document…"
    return f"Using {name}…"


def _tool_summary(block: ToolUseBlock) -> str:
    """A short plain-language description of a tool call, for the activity feed."""
    args = block.input if isinstance(block.input, dict) else {}
    name = block.name
    if name == "Bash":
        cmd = str(args.get("command", "")).strip().replace("\n", " ")
        return f"Running: {cmd[:120]}" if cmd else "Running a command"
    if name == "Write":
        return f"Writing {args.get('file_path', 'a file')}"
    if name == "Edit":
        return f"Editing {args.get('file_path', 'a file')}"
    if name == "Read":
        return f"Reading {args.get('file_path', 'a file')}"
    if name == "Glob":
        return f"Searching files ({args.get('pattern', '')})".strip()
    if name.endswith("query_finance_db"):
        sql = str(args.get("sql", "")).strip().replace("\n", " ")
        return f"Querying database: {sql[:120]}" if sql else "Querying the database"
    if name.endswith("save_document"):
        title = str(args.get("title", "")).strip()
        return f"Writing document: {title}" if title else "Writing a document"
    return f"Using {name}"


def _tool_result_text(block: ToolResultBlock) -> str:
    if isinstance(block.content, str):
        return block.content
    if isinstance(block.content, list):
        return "\n".join(
            item.get("text", "")
            for item in block.content
            if isinstance(item, dict) and item.get("type") == "text"
        )
    return ""


def _parse_document_event(block: ToolResultBlock) -> dict | None:
    """If a ToolResultBlock is the result of save_document, extract its metadata
    marker (a JSON blob on the first line, see app/tools/documents.py) so the
    frontend can render the document as part of the reply instead of raw text."""
    text = _tool_result_text(block).strip()
    if not text:
        return None
    try:
        data = json.loads(text.splitlines()[0])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or "document_id" not in data:
        return None
    doc_id = data["document_id"]
    return {
        "type": "document",
        "id": doc_id,
        "title": data.get("title", ""),
        "doc_type": data.get("doc_type", "html"),
        "url": f"/api/documents/{doc_id}/content",
    }


async def _get_history(session: AsyncSession, session_id: int) -> list[ChatMessage]:
    result = await session.execute(
        select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.id)
    )
    return list(result.scalars().all())


def _build_prompt(
    history: list[ChatMessage], new_content: str, attachments: list[Attachment] | None
) -> str:
    lines = []
    if history:
        lines.append("For context, here is the recent conversation history:\n")
        for m in history[-10:]:
            speaker = "User" if m.role == "user" else "Agent"
            lines.append(f"{speaker}: {m.content}\n")
        lines.append("---\n\nNow continue the conversation. The user's new message is:\n")
    lines.append(new_content)
    if attachments:
        lines.append("\n\nThe user has attached the following file(s). Use the Read tool to open them (paths are relative to the project root):")
        for a in attachments:
            lines.append(f"- {a.filename}: {a.path}")
    return "\n".join(lines)


@app.post("/api/chat/sessions/{session_id}/messages")
async def send_message(
    session_id: int,
    body: NewMessageRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    chat_session = await session.get(ChatSession, session_id)
    if chat_session is None or chat_session.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")

    history = await _get_history(session, session_id)
    prompt = _build_prompt(history, body.content, body.attachments)

    overrides = await get_settings(
        session,
        [
            "llm_primary_base_url",
            "llm_primary_api_key",
            "llm_backup_base_url",
            "llm_backup_api_key",
            "github_token",
        ],
    )
    backup_available = bool(overrides["llm_backup_base_url"] and overrides["llm_backup_api_key"])

    attachments_json = (
        json.dumps([a.model_dump() for a in body.attachments]) if body.attachments else None
    )
    user_msg = ChatMessage(
        session_id=session_id, role="user", content=body.content, attachments=attachments_json
    )
    session.add(user_msg)
    await session.commit()

    new_title = body.content[:80] if chat_session.title is None else None
    resolved_model = body.model if body.model in AVAILABLE_MODELS else settings.finance_agent_model

    async def event_stream():
        reply_text_parts: list[str] = []
        output_started = False
        usage_event: dict | None = None

        async def run(options):
            nonlocal output_started, usage_event
            # DEBUG(temp): tracing a stall where the chat stream stops making
            # progress mid-turn. Logs every SDK message with elapsed/delta
            # timing to stdout (visible via `railway logs`) so the next
            # occurrence pinpoints whether the model is still generating, a
            # tool call is hung executing, or nothing more ever arrives.
            # Remove this whole block (search "DEBUG(temp)") once resolved.
            dbg_t0 = time.monotonic()
            dbg_last = [dbg_t0]

            def dbg(msg: str) -> None:
                now = time.monotonic()
                print(
                    f"[chat-debug] +{now - dbg_t0:6.1f}s (Δ{now - dbg_last[0]:5.1f}s) {msg}",
                    flush=True,
                )
                dbg_last[0] = now

            agen = query(prompt=prompt, options=options).__aiter__()
            next_message = asyncio.ensure_future(agen.__anext__())
            try:
                while True:
                    try:
                        message = await asyncio.wait_for(
                            asyncio.shield(next_message), timeout=PING_INTERVAL_SECONDS
                        )
                    except asyncio.TimeoutError:
                        # The SDK hasn't produced a message in a while - most
                        # likely the model is generating a large tool call
                        # (e.g. save_document writing a full report) with no
                        # delta events along the way, so the client would
                        # otherwise see total silence. Send a keepalive so
                        # proxies/browsers don't treat the connection as idle
                        # and drop it, leaving the UI stuck forever.
                        dbg("no SDK message yet (ping)")
                        yield json.dumps({"type": "ping"}) + "\n"
                        continue
                    except StopAsyncIteration:
                        dbg("agen exhausted (StopAsyncIteration)")
                        break
                    next_message = asyncio.ensure_future(agen.__anext__())

                    if isinstance(message, StreamEvent):
                        event = message.event
                        if event.get("type") == "content_block_start":
                            block = event.get("content_block", {})
                            dbg(f"content_block_start type={block.get('type')} name={block.get('name')}")
                            if block.get("type") == "text" and reply_text_parts:
                                output_started = True
                                yield json.dumps({"type": "delta", "text": "\n\n"}) + "\n"
                            elif block.get("type") == "tool_use":
                                # Announce the tool call the moment it starts,
                                # not after its full input has streamed in -
                                # see _tool_start_summary.
                                output_started = True
                                name = block.get("name", "")
                                yield json.dumps(
                                    {"type": "tool", "name": name, "summary": _tool_start_summary(name)}
                                ) + "\n"
                        elif event.get("type") == "content_block_delta":
                            delta = event.get("delta", {})
                            if delta.get("type") == "text_delta" and delta.get("text"):
                                output_started = True
                                yield json.dumps({"type": "delta", "text": delta["text"]}) + "\n"
                        elif event.get("type") in ("content_block_stop", "message_delta", "message_stop"):
                            dbg(f"{event.get('type')} extra={ {k: v for k, v in event.items() if k not in ('type',)} }")
                    elif isinstance(message, AssistantMessage):
                        dbg(f"AssistantMessage blocks={[type(b).__name__ for b in message.content]}")
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                reply_text_parts.append(block.text)
                            elif isinstance(block, ToolUseBlock):
                                # Surface build activity to the UI. Treat a tool call as
                                # output so a mid-run failure does not re-run the (possibly
                                # side-effectful) turn on the backup provider.
                                output_started = True
                                dbg(f"ToolUseBlock name={block.name} input_keys={list(block.input) if isinstance(block.input, dict) else block.input}")
                                yield json.dumps(
                                    {"type": "tool", "name": block.name, "summary": _tool_summary(block)}
                                ) + "\n"
                    elif isinstance(message, UserMessage):
                        blocks = message.content if isinstance(message.content, list) else []
                        for block in blocks:
                            if isinstance(block, ToolResultBlock):
                                text_len = len(_tool_result_text(block))
                                dbg(f"ToolResultBlock is_error={block.is_error} text_len={text_len}")
                                doc_event = _parse_document_event(block)
                                if doc_event:
                                    yield json.dumps(doc_event) + "\n"
                    elif isinstance(message, ResultMessage):
                        dbg(f"ResultMessage subtype={getattr(message, 'subtype', None)}")
                        usage = message.usage or {}
                        usage_event = {
                            "type": "usage",
                            "model": resolved_model,
                            "input_tokens": usage.get("input_tokens") or 0,
                            "output_tokens": usage.get("output_tokens") or 0,
                            "cache_creation_input_tokens": usage.get("cache_creation_input_tokens") or 0,
                            "cache_read_input_tokens": usage.get("cache_read_input_tokens") or 0,
                            "cost_usd": estimate_cost_usd(resolved_model, usage),
                        }
            finally:
                dbg("run() exiting")
                if not next_message.done():
                    next_message.cancel()

        try:
            primary_options = build_options(
                model=body.model,
                effort=body.effort,
                include_partial_messages=True,
                mode=chat_session.mode,
                primary_base_url=overrides["llm_primary_base_url"],
                primary_api_key=overrides["llm_primary_api_key"],
                github_token=overrides["github_token"],
                session_id=session_id,
                user_id=user.id,
            )
            async for chunk in run(primary_options):
                yield chunk
        except Exception as primary_error:
            if output_started or not backup_available:
                yield json.dumps({"type": "error", "message": str(primary_error)}) + "\n"
                return
            yield json.dumps(
                {"type": "notice", "text": "Primary LLM provider failed - retrying with backup provider…"}
            ) + "\n"
            reply_text_parts.clear()
            try:
                backup_options = build_options(
                    model=body.model,
                    effort=body.effort,
                    include_partial_messages=True,
                    use_backup_llm=True,
                    mode=chat_session.mode,
                    backup_base_url=overrides["llm_backup_base_url"],
                    backup_api_key=overrides["llm_backup_api_key"],
                    github_token=overrides["github_token"],
                    session_id=session_id,
                    user_id=user.id,
                )
                async for chunk in run(backup_options):
                    yield chunk
            except Exception as backup_error:
                yield json.dumps(
                    {
                        "type": "error",
                        "message": (
                            f"Both LLM providers failed. Primary: {primary_error}. "
                            f"Backup: {backup_error}"
                        ),
                    }
                ) + "\n"
                return

        if usage_event is not None:
            yield json.dumps(usage_event) + "\n"

        reply_text = "\n".join(reply_text_parts).strip() or "(no response)"

        async with SessionLocal() as db:
            assistant_msg = ChatMessage(session_id=session_id, role="assistant", content=reply_text)
            if usage_event is not None:
                assistant_msg.input_tokens = usage_event["input_tokens"]
                assistant_msg.output_tokens = usage_event["output_tokens"]
                assistant_msg.cache_creation_input_tokens = usage_event["cache_creation_input_tokens"]
                assistant_msg.cache_read_input_tokens = usage_event["cache_read_input_tokens"]
                assistant_msg.cost_usd = usage_event["cost_usd"]
            db.add(assistant_msg)
            if new_title is not None:
                db_session_obj = await db.get(ChatSession, session_id)
                db_session_obj.title = new_title
            await db.commit()

        yield json.dumps({"type": "done", "content": reply_text, "title": new_title}) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/mobile")
async def mobile_demo():
    return FileResponse(str(STATIC_DIR / "mobile-demo.html"))
