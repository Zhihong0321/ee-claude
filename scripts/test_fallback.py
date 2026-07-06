"""Test: does a genuinely wrong primary auth token cause a real failure,
and does the backup provider succeed with a real finance-agent question?

Uses the actual build_options() (same as production) so system_prompt/cwd/
tools match reality, rather than a bare-bones ClaudeAgentOptions.
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

for _var in ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN"):
    os.environ.pop(_var, None)

from claude_agent_sdk import AssistantMessage, TextBlock, query

from app.config import settings

QUESTION = "How many rows are in the agent table? Answer with just the number, no explanation."


async def run(options):
    reply_parts = []
    async for message in query(prompt=QUESTION, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    reply_parts.append(block.text)
    return "\n".join(reply_parts)


async def main():
    from app.agent import build_options

    print("=== Test 1: real primary (cavoti.com) - should answer 192 ===")
    try:
        result = await run(build_options())
        print(f"Result: {result!r}")
    except Exception as e:
        print(f"FAILED (unexpected): {type(e).__name__}: {e}")

    print()
    print("=== Test 2: primary with deliberately WRONG auth token - should FAIL ===")
    real_token = settings.anthropic_auth_token
    settings.anthropic_auth_token = "sk-deliberately-wrong-00000000000000000000"
    try:
        result = await run(build_options())
        print(f"UNEXPECTED SUCCESS with wrong token: {result!r}")
    except Exception as e:
        print(f"Failed as expected: {type(e).__name__}: {e}")
    finally:
        settings.anthropic_auth_token = real_token

    print()
    print("=== Test 3: real backup (orbitlink.me) - should answer 192 ===")
    try:
        result = await run(build_options(use_backup_llm=True))
        print(f"Result: {result!r}")
    except Exception as e:
        print(f"FAILED (unexpected): {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
