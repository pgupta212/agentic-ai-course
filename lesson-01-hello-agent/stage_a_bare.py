import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()  # reads ANTHROPIC_API_KEY from your .env file

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

messages = [
    {"role": "user", "content": "What is a token in LLMs? Answer in 2 sentences."}
]

response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=256,
    messages=messages
)

print("=== RESPONSE ===")
print(response.content[0].text)
print()
print("=== USAGE ===")
print(f"Input tokens : {response.usage.input_tokens}")
print(f"Output tokens: {response.usage.output_tokens}")
