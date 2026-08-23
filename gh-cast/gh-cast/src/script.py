"""Generate a 2-speaker podcast script from a diff, via Groq.
Ported directly from the original GitCast backend's generate_podcast_script()."""
import re
import sys
from groq import Groq

from config import get_groq_api_key

SYSTEM_PROMPT = (
    "You are an expert tech podcast producer. Convert the provided Git diff into a lively, "
    "concise 2-speaker podcast script (3-4 exchanges total). "
    "Host 1: Senior (Alex - knowledgeable, overarching architecture view). "
    "Host 2: Junior (Sam - enthusiastic, asks questions, points out specific code fixes). "
    "Format your output STRICTLY as line-by-line simple dialogue format:\n"
    "Senior: <text>\nJunior: <text>"
)

SPEAKER_REGEX = re.compile(r"^[*_]*\s*(Senior|Junior)\s*[*_]*\s*:\s*(.*)$", re.IGNORECASE)


def generate_podcast_script(diff_text: str) -> list[dict]:
    api_key = get_groq_api_key()
    if not api_key:
        print(
            "Error: no Groq API key found. Run `gh cast config set groq-api-key <key>` "
            "or set the GROQ_API_KEY environment variable.",
            file=sys.stderr,
        )
        sys.exit(1)

    client = Groq(api_key=api_key)

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Here is the Git Diff:\n\n{diff_text}"},
        ],
        temperature=0.7,
    )

    raw_text = response.choices[0].message.content
    transcript = []

    for line in raw_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        match = SPEAKER_REGEX.match(line)
        if not match:
            continue
        speaker = match.group(1).capitalize()
        text = match.group(2).strip()
        for marker in ("**", "__"):
            if line.startswith(marker) and text.startswith(marker):
                text = text[len(marker):].strip()
        for marker in ("*", "_"):
            if line.startswith(marker) and text.startswith(marker):
                text = text[len(marker):].strip()
        transcript.append({"speaker": speaker, "text": text})

    if not transcript:
        transcript = [
            {"speaker": "Senior", "text": "Welcome! Today we are reviewing this code change."},
            {"speaker": "Junior", "text": "Looks like we refactored the module and improved performance!"},
        ]

    return transcript
