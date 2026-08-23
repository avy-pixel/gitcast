#!/usr/bin/env python3
import argparse
import os
import platform
import subprocess
import sys
import tempfile

from diff import get_pr_diff
from script import generate_podcast_script
from audio import generate_audio_file
from config import set_groq_api_key


def cmd_pr(args):
    print(f"Fetching diff for PR {args.pr_number}...", file=sys.stderr)
    diff_text = get_pr_diff(args.pr_number, repo=args.repo)

    print("Writing podcast script...", file=sys.stderr)
    transcript = generate_podcast_script(diff_text)

    for line in transcript:
        print(f"{line['speaker']}: {line['text']}")

    if args.text_only:
        return

    out_dir = args.out or os.path.join(tempfile.gettempdir(), "gitcast")
    print("Recording audio...", file=sys.stderr)
    audio_path = generate_audio_file(transcript, out_dir)
    print(f"Saved: {audio_path}", file=sys.stderr)

    if args.play:
        _play(audio_path)

    if args.comment:
        _post_comment(args.pr_number, args.repo, transcript)


def _play(path: str):
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.run(["afplay", path])
        elif system == "Linux":
            subprocess.run(["xdg-open", path])
        elif system == "Windows":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            print(f"Don't know how to auto-play on {system}. File is at: {path}", file=sys.stderr)
    except FileNotFoundError:
        print(f"Couldn't find a player for this OS. File is at: {path}", file=sys.stderr)


def _post_comment(pr_number: str, repo: str | None, transcript: list[dict]):
    body_lines = ["🎙️ **GitCast summary**", ""]
    for line in transcript:
        body_lines.append(f"**{line['speaker']}:** {line['text']}")
    body = "\n".join(body_lines)

    cmd = ["gh", "pr", "comment", str(pr_number), "--body", body]
    if repo:
        cmd += ["--repo", repo]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error posting comment: {result.stderr.strip()}", file=sys.stderr)
    else:
        print("Posted summary comment on the PR.", file=sys.stderr)


def cmd_config_set(args):
    if args.key == "groq-api-key":
        set_groq_api_key(args.value)
        print("Saved Groq API key to ~/.config/gh-cast/config.json")
    else:
        print(f"Unknown config key: {args.key}", file=sys.stderr)
        sys.exit(1)


def build_parser():
    parser = argparse.ArgumentParser(prog="gh cast", description="Turn a GitHub PR into a 2-speaker podcast.")
    sub = parser.add_subparsers(dest="command", required=True)

    pr = sub.add_parser("pr", help="Generate a podcast for a PR")
    pr.add_argument("pr_number", help="PR number, e.g. 124")
    pr.add_argument("--repo", help="owner/repo (defaults to the current repo)")
    pr.add_argument("--play", action="store_true", help="Play the audio after generating it")
    pr.add_argument("--text-only", action="store_true", help="Skip audio generation, just print the script")
    pr.add_argument("--comment", action="store_true", help="Post the transcript back on the PR")
    pr.add_argument("--out", help="Directory to save the MP3 (default: system temp dir)")
    pr.set_defaults(func=cmd_pr)

    config = sub.add_parser("config", help="Manage gh-cast settings")
    config_sub = config.add_subparsers(dest="config_command", required=True)
    config_set = config_sub.add_parser("set", help="Set a config value")
    config_set.add_argument("key", choices=["groq-api-key"])
    config_set.add_argument("value")
    config_set.set_defaults(func=cmd_config_set)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
