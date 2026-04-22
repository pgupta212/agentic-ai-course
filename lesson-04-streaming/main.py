"""
Lesson 04 — Streaming FastAPI Server
======================================
A FastAPI backend that streams Claude responses to the browser.

Flow:
  Browser → POST /chat → FastAPI → Anthropic API → Claude
  Claude  → tokens    → FastAPI → SSE            → Browser
"""

import os
from dotenv import load_dotenv
from anthropic import Anthropic
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

app = FastAPI()
client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# Allow browser to talk to our local server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------
# Request model — what the browser sends us
# -----------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str
    history: list = []


# -----------------------------------------------------------------------
# SSE streaming endpoint
# -----------------------------------------------------------------------
@app.post("/chat")
async def chat(request: ChatRequest):
    """
    Receive a message, stream Claude's response back as SSE.
    
    SSE format — each chunk must be:
      data: your text here\n\n
    Browser's EventSource reads these automatically.
    """

    # Build message history
    messages = request.history + [
        {"role": "user", "content": request.message}
    ]

    def generate():
        """Generator function — yields SSE chunks as Claude streams."""
        with client.messages.stream(
            model="claude-sonnet-4-5",
            max_tokens=2048,
            system="You are a helpful assistant. Be concise and clear.",
            messages=messages,
        ) as stream:
            for chunk in stream.text_stream:
                # SSE format: data: <content>\n\n
                yield f"data: {chunk}\n\n"

            # Signal stream is done
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        }
    )


# -----------------------------------------------------------------------
# Serve the frontend HTML
# -----------------------------------------------------------------------
@app.get("/")
async def index():
    """Serve the chat UI."""
    with open("index.html") as f:
        return HTMLResponse(f.read())