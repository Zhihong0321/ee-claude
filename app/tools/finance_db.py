"""Read-only access to the production finance DB (prod_main) via REST proxy."""

import re
from typing import Annotated, Any

import httpx
from claude_agent_sdk import tool

from app.config import settings

_COMMENT_RE = re.compile(r"(--[^\n]*)|(/\*.*?\*/)", re.DOTALL)
_ALLOWED_START_RE = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
_FORBIDDEN_RE = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|grant|revoke|create|copy|call|do|vacuum|reindex|merge|refresh)\b",
    re.IGNORECASE,
)


def _strip_comments(sql: str) -> str:
    return _COMMENT_RE.sub(" ", sql)


def guard_select_only(sql: str) -> str | None:
    """Returns an error message if the SQL is not a single safe SELECT, else None."""
    stripped = _strip_comments(sql).strip()
    if not stripped:
        return "Empty query."
    # Disallow multiple statements: a semicolon anywhere except as the very last
    # non-whitespace character is a second statement.
    body = stripped[:-1] if stripped.endswith(";") else stripped
    if ";" in body:
        return "Multiple statements are not allowed. Submit exactly one SELECT query."
    if not _ALLOWED_START_RE.match(body):
        return "Only SELECT (or WITH ... SELECT) queries are allowed."
    if _FORBIDDEN_RE.search(body):
        return "Query contains a forbidden keyword. Only read-only SELECT queries are allowed."
    return None


@tool(
    "query_finance_db",
    "Run a read-only SQL SELECT query against the production finance database "
    "(prod_main). Only single SELECT statements are permitted - no writes, no "
    "multiple statements. Use this to look up invoices, payments, and agents. "
    "See workspace/DB_SCHEMA.md for the confirmed schema, join keys, and known "
    "data quirks before writing queries.",
    {"sql": Annotated[str, "A single read-only SQL SELECT statement."]},
)
async def query_finance_db(args: dict[str, Any]) -> dict[str, Any]:
    sql = args["sql"]
    error = guard_select_only(sql)
    if error:
        return {"content": [{"type": "text", "text": f"Query rejected: {error}"}], "is_error": True}

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                settings.finance_db_proxy_url,
                headers={"Authorization": f"Bearer {settings.finance_db_proxy_token}"},
                json={"db_name": settings.finance_db_name, "sql": sql, "params": []},
            )
        except httpx.HTTPError as e:
            return {"content": [{"type": "text", "text": f"DB proxy request failed: {e}"}], "is_error": True}

    if resp.status_code != 200:
        return {
            "content": [{"type": "text", "text": f"DB proxy error {resp.status_code}: {resp.text}"}],
            "is_error": True,
        }

    data = resp.json()
    return {"content": [{"type": "text", "text": str(data)}]}
