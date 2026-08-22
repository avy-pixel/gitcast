// DOM ELEMENTS & GLOBAL STATE
const audioElement = document.getElementById('audio-element');
const playBtn = document.getElementById('play-btn');
const seekBar = document.getElementById('seek-bar');
const currentTimeEl = document.getElementById('current-time');
const totalDurationEl = document.getElementById('total-duration');
const speedBtn = document.getElementById('speed-btn');
const muteBtn = document.getElementById('mute-btn');
const prInput = document.getElementById('pr-url');
const generateBtn = document.getElementById('generate-btn');
const demoBtn = document.getElementById('demo-btn');
const prTitle = document.getElementById('pr-title');
const prAuthor = document.getElementById('pr-author');
const transcriptBox = document.getElementById('transcript-box');
const errorMessage = document.getElementById('error-message');
const canvas = document.getElementById('visualizer-canvas');
const canvasCtx = canvas.getContext('2d');

let isPlaying = false;
let audioCtx;
let analyser;
let source;
let animationFrameId;

const playbackSpeeds = [1.0, 1.25, 1.5, 2.0];
let currentSpeedIndex = 0;
const BACKEND_API_URL = "http://localhost:8000/api/generate";
// 1. HARDCODED DEMO DATA (ZERO-FAIL BACKUP)
const samplePodcast = {
  title: "PR #124: Refactor Auth Middleware",
  author: "Alex (Senior) & Sam (Junior)",
  audioUrl: "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
  transcript: [
    { speaker: "Senior", text: "Welcome back! Today we are looking at PR 124." },
    { speaker: "Junior", text: "Right, we refactored the auth check and fixed the JWT memory leak." },
    { speaker: "Senior", text: "Great work. The execution time dropped by 45 milliseconds!" }
  ]
};
// 2. AUDIO PLAYER & CANVAS VISUALIZER
playBtn.addEventListener('click', () => {
  if (!audioElement.src) {
    showError("Please paste a PR URL or click 'View Demo' first!");
    return;
  }

  if (!audioCtx) initAudioContext();

  if (isPlaying) {
    pauseAudio();
  } else {
    playAudio();
  }
});

function playAudio() {
  audioElement.play();
  isPlaying = true;
  playBtn.innerHTML = '<i class="fa-solid fa-pause"></i>';
  drawVisualizer();
}

function pauseAudio() {
  audioElement.pause();
  isPlaying = false;
  playBtn.innerHTML = '<i class="fa-solid fa-play"></i>';
  cancelAnimationFrame(animationFrameId);
}

// Update Seek Bar & Current Time
audioElement.addEventListener('timeupdate', () => {
  if (audioElement.duration) {
    const progress = (audioElement.currentTime / audioElement.duration) * 100;
    seekBar.value = progress;
    currentTimeEl.textContent = formatTime(audioElement.currentTime);
  }
});

// Duration Metadata Load
audioElement.addEventListener('loadedmetadata', () => {
  totalDurationEl.textContent = formatTime(audioElement.duration);
});

// Seek Track
seekBar.addEventListener('input', () => {
  if (audioElement.duration) {
    audioElement.currentTime = (seekBar.value / 100) * audioElement.duration;
  }
});

// Playback Speed Toggle
speedBtn.addEventListener('click', () => {
  currentSpeedIndex = (currentSpeedIndex + 1) % playbackSpeeds.length;
  const speed = playbackSpeeds[currentSpeedIndex];
  audioElement.playbackRate = speed;
  speedBtn.textContent = `${speed}x`;
});

// Mute Toggle
muteBtn.addEventListener('click', () => {
  audioElement.muted = !audioElement.muted;
  muteBtn.innerHTML = audioElement.muted 
    ? '<i class="fa-solid fa-volume-xmark"></i>' 
    : '<i class="fa-solid fa-volume-high"></i>';
});

function formatTime(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins < 10 ? '0' : ''}${mins}:${secs < 10 ? '0' : ''}${secs}`;
}

// Canvas Audio Visualizer
function initAudioContext() {
  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  analyser = audioCtx.createAnalyser();
  analyser.fftSize = 64;

  source = audioCtx.createMediaElementSource(audioElement);
  source.connect(analyser);
  analyser.connect(audioCtx.destination);
}

function drawVisualizer() {
  canvas.width = canvas.parentElement.clientWidth;
  canvas.height = canvas.parentElement.clientHeight;

  const bufferLength = analyser.frequencyBinCount;
  const dataArray = new Uint8Array(bufferLength);

  function renderFrame() {
    animationFrameId = requestAnimationFrame(renderFrame);
    analyser.getByteFrequencyData(dataArray);

    canvasCtx.clearRect(0, 0, canvas.width, canvas.height);

    const barWidth = (canvas.width / bufferLength) * 1.5;
    let x = 0;

    for (let i = 0; i < bufferLength; i++) {
      const barHeight = (dataArray[i] / 255) * canvas.height * 0.85;

      const gradient = canvasCtx.createLinearGradient(0, canvas.height, 0, 0);
      gradient.addColorStop(0, '#10b981'); // Green
      gradient.addColorStop(1, '#34d399'); // Bright Green

      canvasCtx.fillStyle = gradient;
      canvasCtx.fillRect(x, canvas.height - barHeight, barWidth - 3, barHeight);

      x += barWidth;
    }
  }
  renderFrame();
}

// 3. DATA LOADING & API FETCH LOGIC


// Click "View Demo" Button
demoBtn.addEventListener('click', () => {
  clearError();
  prInput.value = "https://github.com/facebook/react/pull/124";
  loadPodcastData(samplePodcast);
});

// Click "Start Listening" Button
generateBtn.addEventListener('click', async () => {
  const url = prInput.value.trim();
  if (!url) {
    showError("Please enter a valid GitHub Pull Request URL.");
    return;
  }

  clearError();
  generateBtn.disabled = true;
  generateBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Generating...';

  try {
    const response = await fetch(`${BACKEND_API_URL}?pr_url=${encodeURIComponent(url)}`, {
      method: 'POST'
    });

    if (!response.ok) {
      let errMsg = "Failed to fetch audio from server.";
      try {
        const errorData = await response.json();
        if (errorData && errorData.detail) {
          errMsg = errorData.detail;
        }
      } catch (e) {}
      throw new Error(errMsg);
    }

    const data = await response.json();
    loadPodcastData({
      title: `PR Review: ${url.split('/').pop()}`,
      author: "Alex & Sam (AI Hosts)",
      audioUrl: data.audio_url,
      transcript: data.transcript
    });
  } catch (err) {
    console.warn("Error during generation:", err);
    // If the network request failed (e.g. server down), we load the demo backup
    if (err.message && (err.message.includes("Failed to fetch") || err.message.includes("NetworkError") || err.message.includes("fetch"))) {
      showError("Backend API server not reached. Loading demo backup...");
      setTimeout(() => {
        loadPodcastData(samplePodcast);
      }, 1500);
    } else {
      showError(err.message || "An unexpected error occurred.");
    }
  } finally {
    generateBtn.disabled = false;
    generateBtn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Start Listening';
  }
});

// Populate Data & Render Transcript
function loadPodcastData(data) {
  prTitle.textContent = data.title;
  prAuthor.textContent = data.author;
  audioElement.src = data.audioUrl;

  transcriptBox.innerHTML = '';
  data.transcript.forEach(line => {
    const p = document.createElement('p');
    p.className = `transcript-line ${line.speaker.toLowerCase()}`;
    p.innerHTML = `<strong>${line.speaker}:</strong> ${line.text}`;
    transcriptBox.appendChild(p);
  });

  if (!audioCtx) initAudioContext();
  playAudio();
}

function showError(msg) {
  errorMessage.style.display = 'block';
  errorMessage.textContent = msg;
}

function clearError() {
  errorMessage.style.display = 'none';
  errorMessage.textContent = '';
}