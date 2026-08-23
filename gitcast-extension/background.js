// Background service worker.
// Content scripts on github.com are subject to that page's CSP, which can
// block cross-origin fetches to localhost. Routing the request through the
// background service worker avoids that entirely.

const BACKEND_URL = "http://localhost:8000/api/generate";

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "OPEN_PLAYER") {
    chrome.tabs.create({ url: chrome.runtime.getURL("player/player.html") });
    return false;
  }

  if (message.type !== "GENERATE_PODCAST") return false;

  const url = `${BACKEND_URL}?pr_url=${encodeURIComponent(message.prUrl)}`;

  fetch(url, { method: "POST" })
    .then(async (res) => {
      if (!res.ok) {
        let detail = "Failed to generate podcast.";
        try {
          const errJson = await res.json();
          if (errJson?.detail) detail = errJson.detail;
        } catch (_) {}
        throw new Error(detail);
      }
      return res.json();
    })
    .then((data) => sendResponse({ ok: true, data }))
    .catch((err) =>
      sendResponse({
        ok: false,
        error:
          err.message === "Failed to fetch"
            ? "Couldn't reach the GitCast backend. Is it running on http://localhost:8000?"
            : err.message,
      })
    );

  return true; // keep the message channel open for the async response
});
