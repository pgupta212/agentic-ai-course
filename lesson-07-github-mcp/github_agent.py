"""
Lesson 07 — GitHub Agent using custom MCP server
==================================================
Connects to our GitHub MCP server using the MCP client library.

Flow:
  1. Start GitHub MCP server as a subprocess
  2. Connect to it using MCP client
  3. Discover available tools automatically
  4. Pass tools to Claude
  5. Handle tool calls by routing through MCP client
  6. Claude answers with real GitHub data
"""

import os
import sys
import asyncio
from anthropic import Anthropic
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
console = Console()

# -----------------------------------------------------------------------
# Token tracking
# -----------------------------------------------------------------------
total_input_tokens  = 0
total_output_tokens = 0


def update_tokens(input_tokens: int, output_tokens: int):
    global total_input_tokens, total_output_tokens
    total_input_tokens  += input_tokens
    total_output_tokens += output_tokens


# -----------------------------------------------------------------------
# Convert MCP tools to Anthropic tool format
# -----------------------------------------------------------------------
def mcp_tools_to_anthropic(mcp_tools) -> list:
    """Convert MCP tool definitions to Anthropic API format."""
    anthropic_tools = []
    for tool in mcp_tools:
        anthropic_tools.append({
            "name": tool.name,
            "description": tool.description or "",
            "input_schema": tool.inputSchema
        })
    return anthropic_tools


# -----------------------------------------------------------------------
# Agent loop
# -----------------------------------------------------------------------
async def run_agent(user_message: str, conversation_history: list, session: ClientSession, tools: list) -> str:
    """Run one turn of the GitHub agent."""

    messages = conversation_history + [
        {"role": "user", "content": user_message}
    ]

    step = 0

    while True:
        step += 1

        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=4096,
            system=(
                "You are a helpful GitHub assistant. "
                "You have access to the user's GitHub account via tools. "
                "Use tools to answer questions about repos, issues, and PRs. "
                "Be concise and format responses clearly. "
                "When creating issues, always confirm with the user first."
            ),
            tools=tools,
            messages=messages
        )

        update_tokens(response.usage.input_tokens, response.usage.output_tokens)
        console.print(
            f"[dim]Step {step} — stop: {response.stop_reason} | "
            f"tokens in: {response.usage.input_tokens}, "
            f"out: {response.usage.output_tokens}[/dim]"
        )

        # Claude is done
        if response.stop_reason == "end_turn":
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text = block.text
            return final_text

        # Claude wants to use tools
        if response.stop_reason == "tool_use":
            messages.append({
                "role": "assistant",
                "content": response.content
            })

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    console.print(
                        f"  [cyan]→ Tool:[/cyan] {block.name} "
                        f"[dim]{block.input}[/dim]"
                    )

                    # Call the tool through MCP session
                    try:
                        result = await session.call_tool(block.name, block.input)
                        tool_output = result.content[0].text if result.content else "No result"
                    except Exception as e:
                        tool_output = f"Error calling tool: {str(e)}"

                    console.print(f"  [green]← Result:[/green] {tool_output[:120]}...")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": tool_output
                    })

            messages.append({
                "role": "user",
                "content": tool_results
            })


# -----------------------------------------------------------------------
# Main async function
# -----------------------------------------------------------------------
async def main():
    console.print(Panel(
        "[bold]Lesson 07 — GitHub Agent[/bold]\n"
        "[dim]Powered by custom MCP server wrapping GitHub API[/dim]\n\n"
        "[dim]Try asking:[/dim]\n"
        "[dim]  • Show my GitHub profile[/dim]\n"
        "[dim]  • List my repos[/dim]\n"
        "[dim]  • Show open issues in agentic-ai-course[/dim]\n"
        "[dim]  • Create an issue in my repo[/dim]\n\n"
        "[dim]Commands: 'quit' to exit[/dim]",
        border_style="dim",
        expand=False
    ))

    # MCP server parameters — runs github_mcp_server.py as subprocess
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["github_mcp_server.py"],
        env={
            "GITHUB_TOKEN": os.environ.get("GITHUB_TOKEN", ""),
            "PATH": os.environ.get("PATH", ""),
        }
    )

    console.print("[dim]Starting GitHub MCP server...[/dim]")

    # Connect to MCP server — stays alive for entire session
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:

            # Initialize the MCP connection
            await session.initialize()

            # Discover all tools from MCP server
            tools_response = await session.list_tools()
            anthropic_tools = mcp_tools_to_anthropic(tools_response.tools)

            console.print(f"[dim]Connected! {len(anthropic_tools)} tools available:[/dim]")
            for tool in anthropic_tools:
                console.print(f"[dim]  • {tool['name']}[/dim]")
            console.print()

            conversation_history = []

            while True:
                try:
                    user_input = input("\033[1;36mYou:\033[0m ").strip()
                except EOFError:
                    break

                if not user_input:
                    continue

                if user_input.lower() in ("quit", "exit"):
                    console.print(
                        f"\n[dim]Session ended. "
                        f"Tokens — in: {total_input_tokens:,}, "
                        f"out: {total_output_tokens:,}[/dim]"
                    )
                    break

                console.print()
                reply = await run_agent(
                    user_input,
                    conversation_history,
                    session,
                    anthropic_tools
                )

                conversation_history.append({"role": "user", "content": user_input})
                conversation_history.append({"role": "assistant", "content": reply})

                console.print(f"\n[bold green]Claude:[/bold green] {reply}\n")


# -----------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------
if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        console.print("[red]ANTHROPIC_API_KEY not set in .env[/red]")
        sys.exit(1)
    if not os.environ.get("GITHUB_TOKEN"):
        console.print("[red]GITHUB_TOKEN not set in .env[/red]")
        sys.exit(1)

    asyncio.run(main())