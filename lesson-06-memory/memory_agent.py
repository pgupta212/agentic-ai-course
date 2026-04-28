"""
Lesson 06 — Memory & Context Management
=========================================
A persistent chat agent that remembers facts across conversations.

Three memory strategies demonstrated:
1. In-memory    — list in RAM, lost on exit
2. File-based   — saved to memory.json, persists across restarts
3. Summarization — compresses old history when context gets too long

Run modes:
  python3 memory_agent.py          — normal mode (file-based memory)
  python3 memory_agent.py --fresh  — start with empty memory
  python3 memory_agent.py --stats  — show memory stats and exit
"""

import os
import sys
import json
import datetime
from anthropic import Anthropic
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

load_dotenv()

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
console = Console()

# -----------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------
MEMORY_FILE       = "memory.json"   # where we persist history
MAX_HISTORY_TURNS = 20              # max conversation turns before summarizing
SUMMARIZE_TO      = 5               # keep last N turns after summarizing
MODEL             = "claude-sonnet-4-5"

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
# Strategy 1: In-memory
# Simple list — fast, lost when program exits
# C++ equivalent: std::vector<Message> in RAM
# -----------------------------------------------------------------------
class InMemoryStore:
    def __init__(self):
        self.messages = []

    def add(self, role: str, content: str):
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.datetime.now().isoformat()
        })

    def get_messages(self) -> list:
        # Return without timestamps — API only wants role + content
        return [{"role": m["role"], "content": m["content"]} for m in self.messages]

    def count(self) -> int:
        return len(self.messages)

    def clear(self):
        self.messages = []


# -----------------------------------------------------------------------
# Strategy 2: File-based memory
# Saves to JSON on disk — persists across restarts
# C++ equivalent: serialize std::vector to disk with nlohmann/json
# -----------------------------------------------------------------------
class FileMemoryStore:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.messages = self._load()

    def _load(self) -> list:
        """Load messages from disk."""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r") as f:
                    data = json.load(f)
                    console.print(
                        f"[dim]Loaded {len(data)} messages from {self.filepath}[/dim]"
                    )
                    return data
            except Exception as e:
                console.print(f"[yellow]Could not load memory: {e}. Starting fresh.[/yellow]")
        return []

    def _save(self):
        """Save messages to disk after every turn."""
        with open(self.filepath, "w") as f:
            json.dump(self.messages, f, indent=2)

    def add(self, role: str, content: str):
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.datetime.now().isoformat()
        })
        self._save()  # persist immediately

    def get_messages(self) -> list:
        return [{"role": m["role"], "content": m["content"]} for m in self.messages]

    def count(self) -> int:
        return len(self.messages)

    def clear(self):
        self.messages = []
        if os.path.exists(self.filepath):
            os.remove(self.filepath)

    def stats(self):
        """Print memory statistics."""
        table = Table(title="Memory Stats", border_style="dim")
        table.add_column("Item",  style="dim")
        table.add_column("Value", justify="right")

        total_chars = sum(len(m["content"]) for m in self.messages)
        est_tokens  = total_chars // 4

        table.add_row("Messages stored",    str(len(self.messages)))
        table.add_row("Total characters",   f"{total_chars:,}")
        table.add_row("Estimated tokens",   f"{est_tokens:,}")
        table.add_row("Memory file",        self.filepath)

        if self.messages:
            first = self.messages[0].get("timestamp", "unknown")
            last  = self.messages[-1].get("timestamp", "unknown")
            table.add_row("First message", first[:19])
            table.add_row("Last message",  last[:19])

        console.print(table)


# -----------------------------------------------------------------------
# Strategy 3: Summarization
# When history gets too long, compress old messages into a summary
# Keeps context window manageable for long-running agents
# C++ equivalent: LRU cache with compression of evicted entries
# -----------------------------------------------------------------------
def summarize_history(messages: list) -> list:
    """
    Compress old messages into a summary.
    Keeps the last SUMMARIZE_TO turns intact.
    Returns a new, shorter message list.
    """
    if len(messages) <= SUMMARIZE_TO * 2:
        return messages

    # Split: old messages to summarize + recent messages to keep
    keep_count    = SUMMARIZE_TO * 2  # keep last N turns (user + assistant pairs)
    old_messages  = messages[:-keep_count]
    recent_messages = messages[-keep_count:]

    console.print(
        f"[dim]Context window management: summarizing {len(old_messages)} "
        f"old messages, keeping {len(recent_messages)} recent...[/dim]"
    )

    # Ask Claude to summarize the old messages
    old_text = "\n".join([
        f"{m['role'].upper()}: {m['content']}" for m in old_messages
    ])

    summary_response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": (
                f"Summarize this conversation history concisely, "
                f"preserving all important facts, names, and context:\n\n{old_text}"
            )
        }]
    )
    update_tokens(
        summary_response.usage.input_tokens,
        summary_response.usage.output_tokens
    )

    summary_text = summary_response.content[0].text

    # Replace old messages with a single summary message
    summary_message = {
        "role": "user",
        "content": f"[Previous conversation summary]: {summary_text}"
    }
    # Add a fake assistant acknowledgment so history alternates correctly
    ack_message = {
        "role": "assistant",
        "content": "Understood. I have the context from our previous conversation."
    }

    new_history = [summary_message, ack_message] + recent_messages
    console.print(
        f"[dim]Summarized: {len(messages)} messages → {len(new_history)} messages[/dim]"
    )
    return new_history


# -----------------------------------------------------------------------
# Main agent — uses file-based memory + summarization
# -----------------------------------------------------------------------
def run_agent(user_input: str, memory: FileMemoryStore) -> str:
    """Send a message, get a response, update memory."""

    # Get current history
    messages = memory.get_messages()

    # Add user message
    messages.append({"role": "user", "content": user_input})

    # Check if we need to summarize
    if len(messages) > MAX_HISTORY_TURNS * 2:
        messages = summarize_history(messages)
        # Update stored memory with summarized version
        memory.messages = [
            {**m, "timestamp": datetime.datetime.now().isoformat()}
            for m in messages[:-1]  # exclude the current user message
        ]
        memory._save()

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=(
            "You are a helpful personal assistant with persistent memory. "
            "Remember facts the user tells you across conversations. "
            "If the user mentions their name, preferences, or important details — remember them. "
            "Be concise and friendly."
        ),
        messages=messages
    )

    update_tokens(response.usage.input_tokens, response.usage.output_tokens)

    reply = response.content[0].text

    # Persist both turns to memory
    memory.add("user", user_input)
    memory.add("assistant", reply)

    return reply


# -----------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------
def main():
    # Handle command line args
    fresh = "--fresh" in sys.argv
    stats_only = "--stats" in sys.argv

    # Initialize file-based memory
    memory = FileMemoryStore(MEMORY_FILE)

    if stats_only:
        memory.stats()
        return

    if fresh:
        memory.clear()
        console.print("[dim]Memory cleared. Starting fresh.[/dim]\n")

    console.print(Panel(
        "[bold]Lesson 06 — Persistent Memory Agent[/bold]\n"
        "[dim]Remembers facts across sessions — even after restart[/dim]\n\n"
        "[dim]Commands:[/dim]\n"
        "[dim]  'quit'   — exit[/dim]\n"
        "[dim]  'memory' — show stored history[/dim]\n"
        "[dim]  'stats'  — show memory statistics[/dim]\n"
        "[dim]  'clear'  — wipe memory[/dim]\n"
        "[dim]  'tokens' — show token usage[/dim]",
        border_style="dim",
        expand=False
    ))

    # Show how many messages we're starting with
    if memory.count() > 0:
        console.print(
            f"[dim]Resuming conversation — {memory.count()} messages in memory.[/dim]\n"
        )
    else:
        console.print("[dim]Starting fresh conversation.[/dim]\n")

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
                f"Tokens used — in: {total_input_tokens:,}, "
                f"out: {total_output_tokens:,}[/dim]"
            )
            break

        if user_input.lower() == "memory":
            messages = memory.get_messages()
            console.print(f"\n[dim]{len(messages)} messages in memory:[/dim]")
            for i, m in enumerate(messages):
                preview = m["content"][:60].replace("\n", " ")
                console.print(f"  [dim][{i:2d}] {m['role']:10} {preview}...[/dim]")
            console.print()
            continue

        if user_input.lower() == "stats":
            memory.stats()
            continue

        if user_input.lower() == "clear":
            memory.clear()
            console.print("[dim]Memory cleared.[/dim]\n")
            continue

        if user_input.lower() == "tokens":
            console.print(
                f"[dim]Tokens — in: {total_input_tokens:,}, "
                f"out: {total_output_tokens:,}[/dim]\n"
            )
            continue

        reply = run_agent(user_input, memory)
        console.print(f"\n[bold green]Claude:[/bold green] {reply}\n")


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        console.print("[red]ANTHROPIC_API_KEY not set in .env[/red]")
        sys.exit(1)
    main()