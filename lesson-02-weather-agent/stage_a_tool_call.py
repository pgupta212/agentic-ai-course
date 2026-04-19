"""
Stage A: See the raw tool_use block Claude returns.
Goal: Understand what Claude actually sends back when it wants to use a tool.
"""

import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# Define the tool — like a function signature Claude can read
tools = [
    {
        "name": "get_weather",
        "description": "Gets the current weather for a given city",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "The city name e.g. London, Tokyo, New York"
                }
            },
            "required": ["city"]
        }
    }
]

messages = [
    {"role": "user", "content": "What is the weather in London?"}
]

response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    tools=tools,
    messages=messages
)

print("=== STOP REASON ===")
print(response.stop_reason)  # 'tool_use' instead of 'end_turn'
print()
print("=== CONTENT BLOCKS ===")
for block in response.content:
    print(f"Type: {block.type}")
    if block.type == "tool_use":
        print(f"Tool name : {block.name}")
        print(f"Tool input: {block.input}")
        print(f"Tool ID   : {block.id}")