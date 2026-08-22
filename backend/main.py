import os
import re
import uuid
import time
import asyncio
import requests
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List
from groq import Groq
import edge_tts
from dotenv import load_dotenv
from pydub import AudioSegment
 
load_dotenv()
 
app = FastAPI(title="GitCast Backend API")
 
# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
 
# Robust path resolution for static files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
AUDIO_DIR = os.path.join(STATIC_DIR, "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
 
# Safe Groq client initialization (free tier, no billing needed)
groq_api_key = os.getenv("GROQ_API_KEY")
client = None
if groq_api_key:
    try:
        client = Groq(api_key=groq_api_key)
    except Exception:
        pass
 
# Two distinct edge-tts voices for a 2-speaker effect
SENIOR_VOICE = "en-US-GuyNeural"
JUNIOR_VOICE = "en-US-JennyNeural"
 
 
class DialogueLine(BaseModel):
    speaker: str
    text: str
 
 
class PodcastResponse(BaseModel):
    audio_url: str
    transcript: List[DialogueLine]
 
 
# ==========================================
# HELPER 1: FETCH GITHUB PR DIFF
# ==========================================
def fetch_github_diff(pr_url: str) -> str:
    """Parses GitHub PR URL and fetches the raw diff."""
    pattern = r"github\.com/([^/]+)/([^/]+)/pull/(\d+)"
    match = re.search(pattern, pr_url)
    if not match:
        raise HTTPException(status_code=400, detail="Invalid GitHub Pull Request URL.")
 
    owner, repo, pr_number = match.groups()
    api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
 
    headers = {"Accept": "application/vnd.github.v3.diff"}
    response = requests.get(api_url, headers=headers)
 
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to fetch PR diff from GitHub.")
 
    return response.text[:4000]
 
 
# ==========================================
# HELPER 2: GENERATE DIALOGUE SCRIPT (Groq, free)
# ==========================================
def generate_podcast_script(diff_text: str) -> List[dict]:
    """Generates a 2-speaker conversation script using Groq's free Llama model."""
    if not client:
        raise HTTPException(
            status_code=500,
            detail="Groq API key is missing. Please set the GROQ_API_KEY environment variable in your .env file."
        )
 
    system_prompt = (
        "You are an expert tech podcast producer. Convert the provided Git diff into a lively, "
        "concise 2-speaker podcast script (3-4 exchanges total). "
        "Host 1: Senior (Alex - knowledgeable, overarching architecture view). "
        "Host 2: Junior (Sam - enthusiastic, asks questions, points out specific code fixes). "
        "Format your output STRICTLY as line-by-line simple dialogue format:\n"
        "Senior: <text>\nJunior: <text>"
    )
 
    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Here is the Git Diff:\n\n{diff_text}"}
        ],
        temperature=0.7
    )
 
    raw_text = response.choices[0].message.content
    transcript = []
 
    speaker_regex = re.compile(r"^[*_]*\s*(Senior|Junior)\s*[*_]*\s*:\s*(.*)$", re.IGNORECASE)
 
    for line in raw_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        match = speaker_regex.match(line)
        if match:
            speaker = match.group(1).capitalize()
            text = match.group(2).strip()
 
            if line.startswith("**") and text.startswith("**"):
                text = text[2:].strip()
            elif line.startswith("*") and text.startswith("*"):
                text = text[1:].strip()
            elif line.startswith("__") and text.startswith("__"):
                text = text[2:].strip()
            elif line.startswith("_") and text.startswith("_"):
                text = text[1:].strip()
 
            transcript.append({"speaker": speaker, "text": text})
 
    if not transcript:
        transcript = [
            {"speaker": "Senior", "text": "Welcome! Today we are reviewing this code change."},
            {"speaker": "Junior", "text": "Looks like we refactored the module and improved performance!"}
        ]
 
    return transcript
 
 
# ==========================================
# HELPER 3: GENERATE AUDIO (edge-tts, free, no key)
# ==========================================
async def _synthesize_line(text: str, voice: str, out_path: str):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(out_path)
    # Verify the file was actually written with real content
    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        raise HTTPException(
            status_code=500,
            detail=f"edge-tts failed to generate audio for voice '{voice}'. Check internet connectivity."
        )
 
 
async def generate_audio_file(transcript: List[dict]) -> str:
    """Generates per-line audio with edge-tts and merges into one MP3 using pydub."""
    try:
        now = time.time()
        for f in os.listdir(AUDIO_DIR):
            fpath = os.path.join(AUDIO_DIR, f)
            if os.path.isfile(fpath) and f.startswith("generated_podcast_") and f.endswith(".mp3"):
                if now - os.path.getmtime(fpath) > 900:
                    os.remove(fpath)
    except Exception:
        pass

    file_name = f"generated_podcast_{uuid.uuid4().hex[:12]}.mp3"
    output_path = os.path.join(AUDIO_DIR, file_name)

    part_files = []
    for item in transcript:
        voice = SENIOR_VOICE if item["speaker"] == "Senior" else JUNIOR_VOICE
        part_path = os.path.join(AUDIO_DIR, f"_part_{uuid.uuid4().hex[:8]}.mp3")
        await _synthesize_line(item["text"], voice, part_path)
        part_files.append(part_path)

    # Properly merge using pydub (correct MP3 concatenation, not raw byte-paste)
    combined = AudioSegment.empty()
    for part in part_files:
        combined += AudioSegment.from_mp3(part)
        os.remove(part)

    combined.export(output_path, format="mp3")

    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        raise HTTPException(status_code=500, detail="Final audio file generation failed unexpectedly.")

    return f"/static/audio/{file_name}"
    
 
# ==========================================
# MAIN API ENDPOINT
# ==========================================
@app.post("/api/generate", response_model=PodcastResponse)
async def generate_podcast(request: Request, pr_url: str = Query(..., description="GitHub PR URL")):
    try:
        diff_text = fetch_github_diff(pr_url)
        transcript = generate_podcast_script(diff_text)
        audio_relative_url = await generate_audio_file(transcript)
 
        base_url = str(request.base_url).rstrip("/")
        audio_full_url = f"{base_url}{audio_relative_url}"
 
        return PodcastResponse(
            audio_url=audio_full_url,
            transcript=transcript
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 