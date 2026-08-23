const content = document.getElementById("content");

chrome.storage.local.get("latestPodcast", ({ latestPodcast }) => {
  if (!latestPodcast) {
    content.innerHTML = `<p class="error">No podcast data found. Generate one from a PR page first.</p>`;
    return;
  }

  const { audio_url, transcript } = latestPodcast;
  const lines = (transcript || [])
    .map((l) => `<p class="line"><strong>${escapeHtml(l.speaker)}:</strong> ${escapeHtml(l.text)}</p>`)
    .join("");

  content.innerHTML = `
    <audio controls autoplay src="${audio_url}"></audio>
    ${lines}
  `;
});

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
