FROM python:3.11-slim

# Install system dependencies
# ffmpeg is strictly required by pydub for MP3 stitching and audio export
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency definition and install packages
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend and frontend source trees
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Set working directory to backend
WORKDIR /app/backend

# Create audio storage directory
RUN mkdir -p static/audio

# Port configuration (Render passes PORT as an environment variable)
ENV PORT=8000
EXPOSE 8000

# Start FastAPI with Uvicorn, listening on all interfaces with forwarded headers support
CMD sh -c "uvicorn main:app --host 0.0.0.0 --port ${PORT} --proxy-headers"
