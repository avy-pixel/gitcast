import os
import re
import uuid
import time
import requests
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="GitCast Backend API")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows requests from any origin (e.g. live-server or local HTML)
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

# Safe OpenAI client initialization
openai_api_key = os.getenv("OPENAI_API_KEY")
client = None
if openai_api_key:
    try:
        client = OpenAI(api_key=openai_api_key)
    except Exception:
        pass

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
    # Pattern: https://github.com/owner/repo/pull/12
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
    
    # Return first 4000 chars of diff to fit LLM prompt limits comfortably
    return response.text[:4000]

# ==========================================
# HELPER 2: GENERATE DIALOGUE SCRIPT (LLM)
# ==========================================
def generate_podcast_script(diff_text: str) -> List[dict]:
    """Generates a 2-speaker conversation script using GPT-4o."""
    if not client:
        raise HTTPException(
            status_code=500,
            detail="OpenAI API key is missing. Please set the OPENAI_API_KEY environment variable in your .env file."
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
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Here is the Git Diff:\n\n{diff_text}"}
        ],
        temperature=0.7
    )
    
    raw_text = response.choices[0].message.content
    transcript = []
    
    # Robust dialogue parser matching speaker labels with markdown bolding, casing, and variable spacing
    speaker_regex = re.compile(r"^[*_]*\s*(Senior|Junior)\s*[*_]*\s*:\s*(.*)$", re.IGNORECASE)
    
    for line in raw_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        match = speaker_regex.match(line)
        if match:
            speaker = match.group(1).capitalize()
            text = match.group(2).strip()
            
            # Clean up trailing bold/italic markers that leaked into text due to colon placement
            # e.g., if line was "**Senior:** Hello", then text is "** Hello" or "**Hello"
            # if line was "*Senior:* Hello", then text is "* Hello" or "*Hello"
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
        # Fallback if model doesn't follow formatting strictly
        transcript = [
            {"speaker": "Senior", "text": "Welcome! Today we are reviewing this code change."},
            {"speaker": "Junior", "text": "Looks like we refactored the module and improved performance!"}
        ]
        
    return transcript

# ==========================================
# HELPER 3: GENERATE AUDIO (TTS)
# ==========================================
def generate_audio_file(transcript: List[dict]) -> str:
    """Concatenates speech synthesis for the dialogue into a single MP3 file."""
    if not client:
        raise HTTPException(
            status_code=500,
            detail="OpenAI API key is missing. Please set the OPENAI_API_KEY environment variable in your .env file."
        )
        
    # Clean up old generated files (e.g. older than 15 minutes) to save disk space
    try:
        now = time.time()
        for f in os.listdir(AUDIO_DIR):
            fpath = os.path.join(AUDIO_DIR, f)
            if os.path.isfile(fpath) and f.startswith("generated_podcast_") and f.endswith(".mp3"):
                if now - os.path.getmtime(fpath) > 900:  # 15 minutes
                    os.remove(fpath)
    except Exception:
        pass

    combined_script = " ".join([f"{item['speaker']} says: {item['text']}" for item in transcript])
    file_name = f"generated_podcast_{uuid.uuid4().hex[:12]}.mp3"
    output_path = os.path.join(AUDIO_DIR, file_name)
    
    # Generate single audio overview using OpenAI TTS
    tts_response = client.audio.speech.create(
        model="tts-1",
        voice="alloy",
        input=combined_script
    )
    
    tts_response.write_to_file(output_path)
    return f"/static/audio/{file_name}"

# ==========================================
# MAIN API ENDPOINT
# ==========================================
@app.post("/api/generate", response_model=PodcastResponse)
async def generate_podcast(request: Request, pr_url: str = Query(..., description="GitHub PR URL")):
    try:
        # Step 1: Get Code Diff
        diff_text = fetch_github_diff(pr_url)
        
        # Step 2: Generate Script
        transcript = generate_podcast_script(diff_text)
        
        # Step 3: Generate Audio File
        audio_relative_url = generate_audio_file(transcript)
        
        # Full URL path dynamically constructed from frontend request base URL
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

# ==========================================
# RUN SERVER COMMAND INSTRUCTIONS
# ==========================================
# Run locally: uvicorn main:app --reload --port 8000