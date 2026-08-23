// Runs on every github.com/*/pull/* page.
// Injects a floating "🎙️ Listen to this PR" button rather than trying to
// slot into GitHub's own DOM structure — GitHub's class names/layout change
// often, so a floating button is far more robust than a precisely-placed one.

function init() {
  if (document.getElementById("gitcast-fab")) return; // already injected

  const fab = document.createElement("button");
  fab.id = "gitcast-fab";
  fab.innerHTML = "🎙️ Listen to this PR";
  document.body.appendChild(fab);

  const panel = document.createElement("div");
  panel.id = "gitcast-panel";
  panel.className = "hidden";
  panel.innerHTML = `
    <h4>GitCast <button id="gitcast-close">✕</button></h4>
    <div id="gitcast-body"><p class="gitcast-status">Click the button to generate a podcast for this PR.</p></div>
  `;
  document.body.appendChild(panel);

  document.getElementById("gitcast-close").addEventListener("click", () => {
    panel.classList.add("hidden");
  });

  fab.addEventListener("click", () => {
    panel.classList.remove("hidden");
    generatePodcast();
  });
}

function generatePodcast() {
  const fab = document.getElementById("gitcast-fab");
  const body = document.getElementById("gitcast-body");

  fab.disabled = true;
  fab.textContent = "Generating…";
  body.innerHTML = `<p class="gitcast-status">Fetching diff, writing script, recording audio… this can take a bit.</p>`;

  chrome.runtime.sendMessage(
    { type: "GENERATE_PODCAST", prUrl: window.location.href },
    (response) => {
      fab.disabled = false;
      fab.innerHTML = "🎙️ Listen to this PR";

      if (!response || !response.ok) {
        const msg = response?.error || "Something went wrong.";
        body.innerHTML = `<p class="gitcast-error">${escapeHtml(msg)}</p>`;
        return;
      }

      const { audio_url, transcript } = response.data;
      const lines = transcript
        .map(
          (l) =>
            `<p class="gitcast-line"><strong>${escapeHtml(l.speaker)}:</strong> ${escapeHtml(l.text)}</p>`
        )
        .join("");

      // GitHub's own Content Security Policy blocks <audio> elements
      // injected into the page from loading a localhost source. So audio
      // is played in a separate extension page (its own CSP) instead --
      // the transcript still shows right here on the PR page.
      chrome.storage.local.set({ latestPodcast: { audio_url, transcript } }, () => {
        chrome.runtime.sendMessage({ type: "OPEN_PLAYER" });
      });

      body.innerHTML = `
        <p class="gitcast-status">Opened the player in a new tab (GitHub blocks audio playback directly on this page).</p>
        ${lines}
      `;
    }
  );
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

init();

// GitHub is a single-page app — re-inject if the user navigates between
// PRs without a full page reload.
let lastUrl = location.href;
new MutationObserver(() => {
  if (location.href !== lastUrl) {
    lastUrl = location.href;
    init();
  }
}).observe(document.body, { childList: true, subtree: true });
