"""gpt-realtime-2 example: audio in / audio out (voice turn) over the Realtime API.

Sends a WAV file as the user's spoken turn and writes the model's spoken
reply to another WAV file, printing the live transcript of both sides.

Requires: pip install websockets>=14

Input WAV must be 24kHz, 16-bit, mono PCM. Convert with:
    ffmpeg -i input.mp3 -ar 24000 -ac 1 -sample_fmt s16 audio.wav

Usage:
    export OPENAI_API_KEY=sk-...
    python gpt_realtime_2_audio_example.py question.wav reply.wav
"""
import asyncio
import base64
import json
import os
import sys
import wave

import websockets

MODEL = "gpt-realtime-2"
URL = f"wss://api.openai.com/v1/realtime?model={MODEL}"
SAMPLE_RATE = 24000
BYTES_PER_SAMPLE = 2
CHUNK_MS = 100


def read_pcm_wav(path: str) -> bytes:
    with wave.open(path, "rb") as wav:
        if (wav.getframerate(), wav.getsampwidth(), wav.getnchannels()) != (SAMPLE_RATE, BYTES_PER_SAMPLE, 1):
            raise ValueError("WAV must be 24kHz, 16-bit, mono PCM")
        return wav.readframes(wav.getnframes())


def write_pcm_wav(path: str, pcm: bytes) -> None:
    with wave.open(path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(BYTES_PER_SAMPLE)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm)


async def run_voice_turn(input_wav: str, output_wav: str) -> None:
    api_key = os.environ["OPENAI_API_KEY"]
    headers = {"Authorization": f"Bearer {api_key}"}
    pcm_in = read_pcm_wav(input_wav)
    chunk_size = int(SAMPLE_RATE * BYTES_PER_SAMPLE * CHUNK_MS / 1000)
    audio_out = bytearray()

    async with websockets.connect(URL, additional_headers=headers) as ws:
        await ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "type": "realtime",
                "output_modalities": ["audio"],
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcm", "rate": SAMPLE_RATE},
                        "turn_detection": None,
                    },
                    "output": {
                        "format": {"type": "audio/pcm"},
                        "voice": "marin",
                    },
                },
            },
        }))

        for i in range(0, len(pcm_in), chunk_size):
            frame = pcm_in[i:i + chunk_size]
            await ws.send(json.dumps({
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(frame).decode("ascii"),
            }))
        await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
        await ws.send(json.dumps({"type": "response.create"}))

        async for raw in ws:
            event = json.loads(raw)
            etype = event.get("type")
            if etype == "response.output_audio.delta":
                audio_out.extend(base64.b64decode(event["delta"]))
            elif etype == "response.output_audio_transcript.delta":
                print(event["delta"], end="", flush=True)
            elif etype == "response.done":
                print()
                break
            elif etype == "error":
                print(f"\n[error] {event['error']}", file=sys.stderr)
                break

    write_pcm_wav(output_wav, bytes(audio_out))
    print(f"Wrote {len(audio_out)} bytes of reply audio to {output_wav}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input-24khz-mono-wav> <output-wav>")
        sys.exit(1)
    asyncio.run(run_voice_turn(sys.argv[1], sys.argv[2]))
