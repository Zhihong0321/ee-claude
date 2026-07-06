"""Interactive terminal chat with the EE Finance Agent, for manual testing."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from claude_agent_sdk import AssistantMessage, ClaudeSDKClient, ResultMessage, TextBlock, ToolUseBlock

from app.agent import build_options


async def main() -> None:
    options = build_options()
    async with ClaudeSDKClient(options=options) as client:
        print("EE Finance Agent ready. Type a question (or 'exit').\n")
        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not user_input or user_input.lower() in ("exit", "quit"):
                break

            await client.query(user_input)
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            print(f"\nAgent: {block.text}\n")
                        elif isinstance(block, ToolUseBlock):
                            print(f"  [tool: {block.name} args={block.input}]")
                elif isinstance(message, ResultMessage):
                    if message.total_cost_usd:
                        print(f"  (cost: ${message.total_cost_usd:.4f})")


if __name__ == "__main__":
    asyncio.run(main())
