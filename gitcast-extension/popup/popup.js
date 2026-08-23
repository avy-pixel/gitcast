const input = document.getElementById("pr-url");
const btn = document.getElementById("generate-btn");
const result = document.getElementById("result");

// Pre-fill with the current tab's URL if it's already a PR page.
chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
  const url = tabs[0]?.url || "";
  if (/github\.com\/[^/]+\/[^/]+\/pull\/\d+/.test(url)) {
    input.value = url;
  }
});

btn.addEventListener("click", () => {
  const prUrl = input.value.trim();
  if (!prUrl) {
    result.innerHTML = `<p class="error">Paste a GitHub PR URL first.</p>`;
    return;
  }

  btn.disabled = true;
  btn.textContent = "Generating…";
  result.innerHTML = `<p class="status">Fetching diff, writing script, recording audio…</p>`;

  chrome.runtime.sendMessage({ type: "GENERATE_PODCAST", prUrl }, (response) => {
    btn.disabled = false;
    btn.textContent = "Generate podcast";

    if (!response || !response.ok) {
      result.innerHTML = `<p class="error">${escapeHtml(response?.error || "Something went wrong.")}</p>`;
      return;
    }

    const { audio_url, transcript } = response.data;
    const lines = transcript
      .map((l) => `<p class="line"><strong>${escapeHtml(l.speaker)}:</strong> ${escapeHtml(l.text)}</p>`)
      .join("");

    // The popup is its own extension page (not injected into github.com),
    // so it isn't subject to GitHub's CSP and can play audio directly.
    result.innerHTML = `<audio controls autoplay src="${audio_url}"></audio>${lines}`;

    chrome.storage.local.set({ latestPodcast: { audio_url, transcript } });
  });
});

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
