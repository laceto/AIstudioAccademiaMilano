"""Minimal gpt-realtime-2 example: interactive text chat over the Realtime API WebSocket.

Requires: pip install websockets>=14

Usage:
    export OPENAI_API_KEY=sk-...
    python gpt_realtime_2_example.py
    > What's the capital of Italy?
    Rome is the capital of Italy.
    > quit
"""
import asyncio
import json
import os
import sys

import websockets

MODEL = "gpt-realtime-2"
URL = f"wss://api.openai.com/v1/realtime?model={MODEL}"


async def _print_responses(ws) -> None:
    async for raw in ws:
        event = json.loads(raw)
        etype = event.get("type")
        if etype == "response.output_text.delta":
            print(event["delta"], end="", flush=True)
        elif etype == "response.done":
            print()
        elif etype == "error":
            print(f"\n[error] {event['error']}", file=sys.stderr)


async def main() -> None:
    api_key = os.environ["OPENAI_API_KEY"]
    headers = {"Authorization": f"Bearer {api_key}"}

    async with websockets.connect(URL, additional_headers=headers) as ws:
        await ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "type": "realtime",
                "output_modalities": ["text"],
                "instructions": "You are a concise, helpful assistant.",
            },
        }))

        recv_task = asyncio.create_task(_print_responses(ws))
        loop = asyncio.get_event_loop()

        while True:
            user_text = await loop.run_in_executor(None, input, "> ")
            if user_text.strip().lower() in {"quit", "exit"}:
                break
            await ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_text}],
                },
            }))
            await ws.send(json.dumps({
                "type": "response.create",
                "response": {"output_modalities": ["text"]},
            }))

        recv_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
