# GitCast Deployment Guide 🚀

GitCast consists of:
1. **FastAPI Backend (Python)**: Fetches PR diffs, calls Groq LLM, generates voice lines via `edge-tts`, and stitches MP3s with `pydub` (which requires `ffmpeg`).
2. **Frontend UI (Static HTML/CSS/JS)**: Audio player, live visualizer canvas, and script transcript.

---

## ⚡ Which Platform Should You Use?

| Platform | Best For | Compatibility Notes |
| :--- | :--- | :--- |
| **Render** *(Recommended)* | **Full Stack (Frontend + Backend)** | ✅ **100% Supported**. Runs Docker container with `ffmpeg` pre-installed, writes audio to disk, and serves both frontend and API from a single URL. |
| **Vercel** | **Frontend Only** | ⚠️ **Frontend only**. Vercel Serverless is not recommended for this backend because it lacks `ffmpeg`, has a read-only filesystem, and enforces a strict 10s timeout on the free tier. |

---

## Option 1: Deploy to Render (Recommended — Full App)

We have configured a `Dockerfile` and `render.yaml` so the entire app (API + Frontend) deploys together in one service.

### Step 1: Push your changes to GitHub
```bash
git add .
git commit -m "Configure Docker and Render deployment"
git push origin main
```

### Step 2: Deploy on Render
1. Go to [Render Dashboard](https://dashboard.render.com/).
2. Click **New +** → **Blueprint** (or **Web Service**).
   - If using **Blueprint**: Select your `gitcast` GitHub repo. Render reads `render.yaml` automatically.
   - If using **Web Service**:
     - Connect your `gitcast` repo.
     - Choose **Docker** as the Runtime (it will use the root `Dockerfile`).
     - Set Region (e.g., Oregon or Frankfurt).
     - Plan: **Free**.
3. In **Environment Variables**, add:
   - `GROQ_API_KEY`: Your Groq API key from [Groq Console](https://console.groq.com/keys).
   - `GITHUB_TOKEN`: *(Optional)* GitHub personal access token for higher rate limits on PR diffs.
4. Click **Create Web Service** / **Apply**.

Once built, Render will give you a live URL (e.g. `https://gitcast-xxxx.onrender.com`).
Opening that URL in your browser will load the full frontend UI, and all API calls will automatically route to the backend!

---

## Option 2: Deploy Frontend on Vercel + Backend on Render

If you prefer hosting the frontend on Vercel and the backend on Render:

### 1. Deploy the Backend on Render
Follow the steps in **Option 1** above to get your Render backend URL (e.g., `https://gitcast-api.onrender.com`).

### 2. Update Backend URL in Frontend
In `frontend/app.js`, ensure `BACKEND_API_URL` points to your Render backend:
```javascript
const BACKEND_API_URL = "https://gitcast-api.onrender.com/api/generate";
```
Commit and push this change to GitHub.

### 3. Deploy Frontend to Vercel
1. Go to [Vercel Dashboard](https://vercel.com/new).
2. Click **Import** next to your `gitcast` repository.
3. In Project Settings:
   - Root Directory: `frontend` (or leave default root, as `vercel.json` handles rewrites automatically).
4. Click **Deploy**.

Vercel will give you a domain like `https://gitcast.vercel.app` pointing to your static frontend.
