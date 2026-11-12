"""Minimal gpt-realtime-whisper example: streaming speech-to-text over the Realtime API.

Requires: pip install websockets>=14

Input WAV must be 24kHz, 16-bit, mono PCM. Convert with:
    ffmpeg -i input.mp3 -ar 24000 -ac 1 -sample_fmt s16 audio.wav

Usage:
    export OPENAI_API_KEY=sk-...
    python gpt_realtime_whisper_example.py audio.wav
"""
import asyncio
import base64
import json
import os
import sys
import wave

import websockets

URL = "wss://api.openai.com/v1/realtime?intent=transcription"
SAMPLE_RATE = 24000
BYTES_PER_SAMPLE = 2
CHUNK_MS = 100


async def _print_transcript(ws) -> None:
    async for raw in ws:
        event = json.loads(raw)
        etype = event.get("type")
        if etype == "conversation.item.input_audio_transcription.delta":
            print(event["delta"], end="", flush=True)
        elif etype == "conversation.item.input_audio_transcription.completed":
            print(f"\n[final] {event['transcript']}")
        elif etype == "error":
            print(f"\n[error] {event['error']}", file=sys.stderr)


async def main(wav_path: str) -> None:
    api_key = os.environ["OPENAI_API_KEY"]
    headers = {"Authorization": f"Bearer {api_key}"}

    with wave.open(wav_path, "rb") as wav:
        if (wav.getframerate(), wav.getsampwidth(), wav.getnchannels()) != (SAMPLE_RATE, BYTES_PER_SAMPLE, 1):
            raise ValueError("WAV must be 24kHz, 16-bit, mono PCM")
        pcm = wav.readframes(wav.getnframes())

    chunk_size = int(SAMPLE_RATE * BYTES_PER_SAMPLE * CHUNK_MS / 1000)

    async with websockets.connect(URL, additional_headers=headers) as ws:
        await ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "type": "transcription",
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcm", "rate": SAMPLE_RATE},
                        "transcription": {"model": "gpt-realtime-whisper", "language": "en"},
                    },
                },
            },
        }))

        recv_task = asyncio.create_task(_print_transcript(ws))

        for i in range(0, len(pcm), chunk_size):
            frame = pcm[i:i + chunk_size]
            await ws.send(json.dumps({
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(frame).decode("ascii"),
            }))
            await asyncio.sleep(CHUNK_MS / 1000)  # paced like real-time mic input

        await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
        await asyncio.sleep(2)  # let the final transcript flush
        recv_task.cancel()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <path-to-24khz-mono-wav>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
