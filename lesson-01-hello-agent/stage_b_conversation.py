import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# This list IS your memory — you own it, you manage it
conversation_history = []

def chat(user_input):
    # Add user message to history
    conversation_history.append({
        "role": "user",
        "content": user_input
    })

    # Send FULL history every time — API is stateless
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        system="You are a helpful assistant. Be concise.",
        messages=conversation_history
    )

    reply = response.content[0].text

    # Add Claude's reply to history
    conversation_history.append({
        "role": "assistant",
        "content": reply
    })

    print(f"Tokens used — in: {response.usage.input_tokens}, out: {response.usage.output_tokens}")
    return reply

print("Chat started. Type 'quit' to exit, 'history' to see message stack.\n")

while True:
    user_input = input("You: ").strip()

    if user_input.lower() == "quit":
        break

    if user_input.lower() == "history":
        print(f"\n--- {len(conversation_history)} messages in history ---")
        for i, msg in enumerate(conversation_history):
            print(f"  [{i}] {msg['role']}: {msg['content'][:60]}...")
        print()
        continue

    reply = chat(user_input)
    print(f"Claude: {reply}\n")