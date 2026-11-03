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
 
def get_groq_client():
    api_key = (os.getenv("GROQ_API_KEY") or "").strip().strip('"').strip("'")
    if not api_key:
        return None
    try:
        return Groq(api_key=api_key)
    except Exception:
        return None
 
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
    token = os.getenv("GITHUB_TOKEN")

    # Strategy 1: If GITHUB_TOKEN is set, use authenticated GitHub API (5,000 req/hr)
    if token:
        api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
        headers = {
            "Accept": "application/vnd.github.v3.diff",
            "Authorization": f"token {token}",
            "User-Agent": "GitCast/1.0"
        }
        try:
            resp = requests.get(api_url, headers=headers, timeout=10)
            if resp.status_code == 200 and resp.text.strip():
                return resp.text[:4000]
        except Exception:
            pass

    # Strategy 2: Direct .diff web URL (bypasses GitHub REST API 60 req/hr IP rate limit completely)
    web_diff_url = f"https://github.com/{owner}/{repo}/pull/{pr_number}.diff"
    web_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(web_diff_url, headers=web_headers, timeout=10, allow_redirects=True)
        if resp.status_code == 200 and resp.text.strip():
            return resp.text[:4000]
    except Exception:
        pass

    # Strategy 3: Unauthenticated REST API fallback
    api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    headers = {
        "Accept": "application/vnd.github.v3.diff",
        "User-Agent": "GitCast/1.0"
    }
    resp = requests.get(api_url, headers=headers, timeout=10)
    if resp.status_code == 200 and resp.text.strip():
        return resp.text[:4000]

    if resp.status_code == 403:
        raise HTTPException(
            status_code=403,
            detail="GitHub rate limit exceeded on public IP. Please add a GITHUB_TOKEN in Render environment variables or try another PR."
        )

    raise HTTPException(
        status_code=400,
        detail=f"GitHub returned {resp.status_code}: {resp.text[:300]}"
    )
 
 
# ==========================================
# HELPER 2: GENERATE DIALOGUE SCRIPT (Groq, free)
# ==========================================
def is_valid_chat_model(model_id: str) -> bool:
    mid = model_id.lower()
    excluded = ["guard", "whisper", "vision", "embed", "safeguard", "moderation", "tts"]
    return not any(ex in mid for ex in excluded)


def get_best_available_model(client: Groq) -> str:
    """Detects the best available chat completion model from Groq dynamically."""
    env_model = os.getenv("GROQ_MODEL")
    if env_model:
        return env_model

    preferred_slugs = [
        "llama-3.1-8b-instant",
        "llama-3.3-70b",
        "llama3-70b",
        "llama3-8b",
        "gpt-oss-20b",
        "qwen3.8-27b",
        "mixtral-8x7b"
    ]

    try:
        models_data = client.models.list()
        available_ids = [m.id for m in models_data.data if getattr(m, 'active', True)]
        
        # 1. Match preferred chat model slugs
        for slug in preferred_slugs:
            for mid in available_ids:
                if slug in mid and is_valid_chat_model(mid):
                    return mid

        # 2. Match any valid text/chat model
        for mid in available_ids:
            if is_valid_chat_model(mid) and any(k in mid.lower() for k in ["llama", "gpt", "qwen", "instruct"]):
                return mid
    except Exception as e:
        print(f"Could not query Groq models: {e}")

    return "llama-3.1-8b-instant"


def generate_podcast_script(diff_text: str) -> List[dict]:
    """Generates a 2-speaker conversation script using Groq's free Llama model."""
    client = get_groq_client()
    if not client:
        raise HTTPException(
            status_code=500,
            detail="Groq API key is missing. Please set the GROQ_API_KEY environment variable in Render."
        )
 
    system_prompt = (
        "You are an expert tech podcast producer. Convert the provided Git diff into a lively, "
        "concise 2-speaker podcast script (3-4 exchanges total). "
        "Host 1: Senior (Alex - knowledgeable, overarching architecture view). "
        "Host 2: Junior (Sam - enthusiastic, asks questions, points out specific code fixes). "
        "Format your output STRICTLY as line-by-line simple dialogue format:\n"
        "Senior: <text>\nJunior: <text>"
    )
 
    model_name = get_best_available_model(client)
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Here is the Git Diff:\n\n{diff_text}"}
            ],
            temperature=0.7
        )
    except Exception as e:
        err_str = str(e)
        if "invalid_api_key" in err_str.lower() or "401" in err_str:
            raise HTTPException(
                status_code=401,
                detail="Invalid Groq API Key. Please verify your GROQ_API_KEY in Render Environment Variables (get a free key at https://console.groq.com/keys)."
            )
        raise HTTPException(status_code=500, detail=f"Groq API error ({model_name}): {err_str[:300]}")
 
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
        try:
          await _synthesize_line(item["text"], voice, part_path)
        except Exception as e:
            print(f"Error occurred while synthesizing line: {e}")
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
        # Ensure HTTPS scheme when deployed behind reverse proxy (Render, Vercel, etc.)
        forwarded_proto = request.headers.get("x-forwarded-proto")
        if forwarded_proto and base_url.startswith("http://"):
            base_url = "https://" + base_url[len("http://"):]
        audio_full_url = f"{base_url}{audio_relative_url}"
 
        return PodcastResponse(
            audio_url=audio_full_url,
            transcript=transcript
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "ok"}


# Mount frontend static files if available (serves full UI + API from one single service)
FRONTEND_DIR = os.path.join(os.path.dirname(BASE_DIR), "frontend")
if not os.path.exists(FRONTEND_DIR):
    FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

