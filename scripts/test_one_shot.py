"""One-shot smoke test: ask the agent a real question, print the full trace."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, ToolUseBlock, query

from app.agent import build_options


async def main() -> None:
    question = sys.argv[1] if len(sys.argv) > 1 else "How many invoices are marked paid=true, and what is the sum of total_amount for them?"
    print(f"Q: {question}\n")
    options = build_options()
    async for message in query(prompt=question, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"Agent: {block.text}\n")
                elif isinstance(block, ToolUseBlock):
                    print(f"  [tool: {block.name} args={block.input}]")
        elif isinstance(message, ResultMessage):
            print(f"--- done. cost=${message.total_cost_usd or 0:.4f} turns={message.num_turns} ---")


if __name__ == "__main__":
    asyncio.run(main())
