import os
import sys
import signal
from dotenv import load_dotenv
from anthropic import Anthropic
from rich.console import Console
from rich.panel import Panel

load_dotenv()

console = Console()
client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

MODEL = "claude-sonnet-4-5"
MAX_TOKENS = 1024

SYSTEM_PROMPT = """You are a focused technical mentor teaching agentic AI to 
a senior C++ developer. Be concise and use systems programming analogies."""

conversation_history = []
total_input_tokens = 0
total_output_tokens = 0


def stream_response(user_input):
    global total_input_tokens, total_output_tokens

    conversation_history.append({
        "role": "user",
        "content": user_input
    })

    full_response = ""

    console.print("\n[bold green]Claude:[/bold green] ", end="")

    # Stream tokens as they arrive
    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=conversation_history,
    ) as stream:
        for chunk in stream.text_stream:
            console.print(chunk, end="")
            full_response += chunk

        final = stream.get_final_message()
        total_input_tokens += final.usage.input_tokens
        total_output_tokens += final.usage.output_tokens
        in_tok = final.usage.input_tokens
        out_tok = final.usage.output_tokens

    console.print(f"\n[dim]  tokens — in: {in_tok}, out: {out_tok} | "
                  f"session total — in: {total_input_tokens}, out: {total_output_tokens}[/dim]\n")

    conversation_history.append({
        "role": "assistant",
        "content": full_response
    })


def handle_exit(sig, frame):
    console.print("\n\n[dim]Session ended.[/dim]")
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, handle_exit)

    console.print(Panel(
        "[bold]Lesson 01 — Streaming Chatbot[/bold]\n"
        "[dim]Commands: 'quit' · 'history' · 'tokens'[/dim]",
        border_style="dim",
        expand=False,
    ))

    while True:
        user_input = input("\033[1;36mYou:\033[0m ").strip()

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit"):
            console.print("[dim]Goodbye.[/dim]")
            break

        if user_input.lower() == "history":
            console.print(f"\n[dim]{len(conversation_history)} messages in history:[/dim]")
            for i, msg in enumerate(conversation_history):
                console.print(f"  [dim][{i}] {msg['role']}: {msg['content'][:60]}...[/dim]")
            console.print()
            continue

        if user_input.lower() == "tokens":
            console.print(f"\n[dim]Session total — in: {total_input_tokens}, "
                          f"out: {total_output_tokens}[/dim]\n")
            continue

        stream_response(user_input)


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        console.print("[red]ANTHROPIC_API_KEY not set in .env[/red]")
        sys.exit(1)
    main()