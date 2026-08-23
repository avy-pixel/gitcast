# GitCast 🎙️

**Your PRs, now in your ears.**

GitCast turns a GitHub pull request into a short, two-host podcast. Paste a PR URL, and it fetches the diff, writes a conversational script between a "Senior" and a "Junior" engineer, and generates real audio you can listen to — with a live transcript alongside the player.

## How it works

1. **Sync** — GitCast fetches the diff for the PR straight from the GitHub API.
2. **Analyze** — The diff is sent to an LLM (via Groq) which writes a short back-and-forth script summarizing the change.
3. **Cast** — Each line is synthesized with a distinct voice (via `edge-tts`) and stitched into a single MP3.

The frontend plays the result with a custom audio player, a live canvas visualizer, and a scrolling transcript.
## Tech stack

| Layer    | Tech |
|----------|------|
| Frontend | Vanilla HTML/CSS/JS, Font Awesome icons, Canvas API for the audio visualizer |
| Backend  | FastAPI (Python) |
| Script generation | [Groq](https://groq.com) API (`openai/gpt-oss-20b`) |
| Text-to-speech | [`edge-tts`](https://github.com/rany2/edge-tts) (free, no API key) |
| Audio merging | `pydub` |

## Project structure

```
git-cast/
├── backend/
│   ├── main.py            # FastAPI app: diff fetching, script + audio generation
│   ├── requirements.txt
│   ├── .env                # GROQ_API_KEY goes here (not committed)
│   └── static/audio/       # Generated podcast MP3s (auto-cleaned after 15 min)
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── style.css
└── requirements.txt
```

## Setup

### Prerequisites

- Python 3.10+
- A free [Groq API key](https://console.groq.com/keys)
- `ffmpeg` installed and on your `PATH` (required by `pydub` for MP3 export)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in `backend/` with:

```
GROQ_API_KEY=your_groq_api_key_here
```

Run the server:

```bash
uvicorn main:app --reload --port 8000
```

The API will be live at `http://localhost:8000`.

### Frontend

The frontend is static — no build step. Just open `frontend/index.html` in a browser, or serve it with any static file server:

```bash
cd frontend
python -m http.server 5500
```

> By default, `app.js` points at `http://localhost:8000/api/generate` for the backend. Update `BACKEND_API_URL` in `app.js` if you're running the backend elsewhere.

## API

### `POST /api/generate`

Generates a podcast from a GitHub PR.

**Query parameter:**

| Name | Type | Description |
|------|------|-------------|
| `pr_url` | string | A GitHub pull request URL, e.g. `https://github.com/owner/repo/pull/123` |

**Response:**

```json
{
  "audio_url": "http://localhost:8000/static/audio/generated_podcast_xxxx.mp3",
  "transcript": [
    { "speaker": "Senior", "text": "Welcome back! Today we are looking at PR 124." },
    { "speaker": "Junior", "text": "Right, we refactored the auth check and fixed the memory leak." }
  ]
}
```

Only the first ~4000 characters of the diff are used to keep script generation fast and within model limits.

## Notes & limitations

- Works with public GitHub PRs only (uses the unauthenticated GitHub API, which is rate-limited).
- Generated audio files are stored in `backend/static/audio/` and auto-deleted after 15 minutes.
- If the backend is unreachable, the frontend falls back to a hardcoded demo podcast so the UI never looks broken.
- No authentication or persistence — this is a demo/prototype, not production-ready as-is.

## License

Not specified — add one if you plan to share or open-source this.
