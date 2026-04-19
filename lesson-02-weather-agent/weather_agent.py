"""
Lesson 02 — Weather Agent
Full agent loop with tool calling and real weather API.
"""

import os
import httpx
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# -----------------------------------------------------------------------
# Tool definition — this is what Claude reads to understand the tool
# -----------------------------------------------------------------------
tools = [
    {
        "name": "get_weather",
        "description": "Gets current weather for a given city",
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


# -----------------------------------------------------------------------
# The actual tool implementation — Claude never sees this code
# Claude only sees the definition above and the result you send back
# -----------------------------------------------------------------------
def get_weather(city: str) -> str:
    """Call Open-Meteo API to get real weather data. No API key needed."""
    
    # Step 1: get coordinates for the city
    geo_url = "https://geocoding-api.open-meteo.com/v1/search"
    geo_response = httpx.get(geo_url, params={"name": city, "count": 1})
    geo_data = geo_response.json()
    
    if not geo_data.get("results"):
        return f"Could not find city: {city}"
    
    location = geo_data["results"][0]
    lat = location["latitude"]
    lon = location["longitude"]
    name = location["name"]
    country = location.get("country", "")
    
    # Step 2: get weather for those coordinates
    weather_url = "https://api.open-meteo.com/v1/forecast"
    weather_response = httpx.get(weather_url, params={
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,weather_code,wind_speed_10m",
        "temperature_unit": "celsius"
    })
    weather_data = weather_response.json()
    current = weather_data["current"]
    
    temp = current["temperature_2m"]
    wind = current["wind_speed_10m"]
    
    return (
        f"Weather in {name}, {country}: "
        f"{temp}°C, wind speed {wind} km/h"
    )


# -----------------------------------------------------------------------
# Tool dispatcher — maps tool names to actual functions
# In C++ terms: a function pointer table / vtable
# -----------------------------------------------------------------------
def call_tool(tool_name: str, tool_input: dict) -> str:
    if tool_name == "get_weather":
        return get_weather(tool_input["city"])
    return f"Unknown tool: {tool_name}"


# -----------------------------------------------------------------------
# The agent loop — the heart of every agentic system
# -----------------------------------------------------------------------
def run_agent(user_message: str):
    print(f"\nUser: {user_message}")
    print("-" * 40)

    messages = [{"role": "user", "content": user_message}]

    # Keep looping until Claude says end_turn
    while True:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            tools=tools,
            messages=messages
        )

        print(f"Stop reason: {response.stop_reason}")

        # Case 1: Claude is done — print final answer
        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    print(f"\nClaude: {block.text}")
            break

        # Case 2: Claude wants to use a tool
        if response.stop_reason == "tool_use":
            # Add Claude's response to history
            messages.append({
                "role": "assistant",
                "content": response.content
            })

            # Find and execute all tool calls
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"Calling tool : {block.name}")
                    print(f"With input   : {block.input}")

                    result = call_tool(block.name, block.input)
                    print(f"Tool result  : {result}")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            # Send tool results back to Claude
            messages.append({
                "role": "user",
                "content": tool_results
            })
            # Loop again — Claude will now give final answer


# -----------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------
if __name__ == "__main__":
    print("=== Lesson 02 — Weather Agent ===\n")
    
    # Test 1: question that needs the tool
    run_agent("What is the weather in Tokyo?")
    
    # Test 2: question that does NOT need the tool
    run_agent("What is the capital of France?")