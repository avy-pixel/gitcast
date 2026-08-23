"""Text-to-speech + merge, ported from the original GitCast backend."""
import asyncio
import os
import sys
import uuid

import edge_tts
from pydub import AudioSegment

SENIOR_VOICE = "en-US-GuyNeural"
JUNIOR_VOICE = "en-US-JennyNeural"


async def _synthesize_line(text: str, voice: str, out_path: str):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(out_path)
    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        print(f"Error: edge-tts failed to generate audio for voice '{voice}'.", file=sys.stderr)
        sys.exit(1)


async def _generate_audio_async(transcript: list[dict], out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    file_name = f"gitcast_{uuid.uuid4().hex[:12]}.mp3"
    output_path = os.path.join(out_dir, file_name)

    part_files = []
    for item in transcript:
        voice = SENIOR_VOICE if item["speaker"] == "Senior" else JUNIOR_VOICE
        part_path = os.path.join(out_dir, f"_part_{uuid.uuid4().hex[:8]}.mp3")
        await _synthesize_line(item["text"], voice, part_path)
        part_files.append(part_path)

    combined = AudioSegment.empty()
    for part in part_files:
        combined += AudioSegment.from_mp3(part)
        os.remove(part)

    combined.export(output_path, format="mp3")

    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        print("Error: final audio file generation failed.", file=sys.stderr)
        sys.exit(1)

    return output_path


def generate_audio_file(transcript: list[dict], out_dir: str) -> str:
    return asyncio.run(_generate_audio_async(transcript, out_dir))
