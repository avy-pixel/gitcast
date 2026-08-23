# GitCast Browser Extension

Adds a floating **🎙️ Listen to this PR** button directly on GitHub PR pages. Click it, and it generates a 2-speaker podcast for that PR using your local GitCast backend — audio player and transcript appear right there on the page.

## How it works

- **`content-script.js`** runs on every `github.com/*/pull/*` page and injects the floating button + panel.
- **`background.js`** is the service worker that actually calls your backend (kept separate from the content script because GitHub's page CSP can block direct fetches to `localhost` from scripts injected into the page).
- **`popup/`** is a fallback UI (click the extension icon in your toolbar) for when you want to paste a PR URL manually instead of navigating to the page.

Both the injected button and the popup call the same backend endpoint your original GitCast app used: `POST http://localhost:8000/api/generate?pr_url=...`.

## Setup

### 1. Start your existing backend

This extension is a frontend only — it needs your FastAPI backend running locally.

```powershell
cd D:\git-cast\backend
.\venv\Scripts\Activate.ps1
uvicorn main:app --reload --port 8000
```

Leave that terminal running. Confirm it's up by visiting `http://localhost:8000/docs` in a browser.

### 2. Load the extension in Chrome

1. Go to `chrome://extensions`
2. Turn on **Developer mode** (top-right toggle)
3. Click **Load unpacked**
4. Select this `gitcast-extension` folder
5. You should see the GitCast icon appear in your toolbar

### 3. Try it

1. Go to any GitHub PR, e.g. `https://github.com/octocat/Hello-World/pull/1`
2. A green **🎙️ Listen to this PR** button appears floating in the bottom-right corner
3. Click it — a panel opens showing progress, then the audio player + transcript once done

Or click the extension icon in your toolbar to open the popup and paste any PR URL manually.

## Troubleshooting

- **"Couldn't reach the GitCast backend"** — your `uvicorn` server isn't running, or it's on a different port than 8000. Check step 1.
- **Button doesn't appear on the PR page** — refresh the page after loading the extension for the first time (extensions only inject into tabs opened/reloaded after install).
- **Nothing happens on click, no error** — open Chrome DevTools (F12) on the PR page and check the Console tab for errors from `content-script.js`.

## Locking down CORS (recommended before sharing this with anyone else)

Right now the backend's `main.py` has:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    ...
)
```

Once you publish this extension (Chrome Web Store gives it a permanent ID), replace `"*"` with `["chrome-extension://<your-permanent-extension-id>"]` so random websites can't call your backend directly.

## Publishing to the Chrome Web Store (later)

1. Zip this folder's contents (not the folder itself — the manifest must be at the zip's root)
2. Create a one-time $5 developer account at the [Chrome Web Store Developer Dashboard](https://chrome.google.com/webstore/devconsole)
3. Upload the zip, fill in a description + the icons already included here, add screenshots
4. Submit for review (usually a few days)

Note: for anyone other than you to use the published version, your backend also needs to be hosted publicly (not `localhost`) — see the earlier roadmap doc for that step if you want to go there.
