"""Fetch PR diffs using the authenticated `gh` CLI instead of raw
unauthenticated GitHub API calls. This removes the rate-limit problem
and adds private-repo support for free, since `gh` is already logged in."""
import subprocess
import sys


def get_pr_diff(pr_number: str, repo: str | None = None, max_chars: int = 4000) -> str:
    cmd = ["gh", "pr", "diff", str(pr_number)]
    if repo:
        cmd += ["--repo", repo]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error: failed to fetch PR diff.\n{result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)

    return result.stdout[:max_chars]
