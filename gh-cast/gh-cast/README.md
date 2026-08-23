# gh-cast

A `gh` CLI extension that turns a GitHub PR into a 2-speaker podcast.

```
gh cast pr 124 --play
```

## Prerequisites

- [`gh`](https://cli.github.com/) installed and authenticated (`gh auth login`)
- Python 3.10+
- `ffmpeg` on your `PATH` (used by `pydub` to export MP3)
- A free [Groq API key](https://console.groq.com/keys)

## Install (as a gh extension, once published)

```bash
gh extension install <your-github-username>/gh-cast
```

## Install (local dev, before publishing)

```bash
git clone https://github.com/<your-github-username>/gh-cast.git
cd gh-cast
pip install -r requirements.txt
gh extension install .
```

## Set your Groq key

```bash
gh cast config set groq-api-key <your-key>
```

(or set the `GROQ_API_KEY` environment variable instead)

## Usage

```bash
gh cast pr 124                      # generate + save MP3, print transcript
gh cast pr 124 --play               # also play it immediately
gh cast pr 124 --repo owner/repo    # PR in a different repo
gh cast pr 124 --text-only          # just print the script, skip TTS
gh cast pr 124 --comment            # also post the transcript as a PR comment
gh cast pr 124 --out ./podcasts     # custom output directory
```

## Publishing this as a real extension

1. Create a new GitHub repo named exactly `gh-cast` (the `gh-` prefix is required).
2. Push this directory's contents to it.
3. Add the topic `gh-extension` to the repo (Settings → General → Topics) so it shows up in `gh extension browse`.
4. Anyone can then run `gh extension install <you>/gh-cast`.
