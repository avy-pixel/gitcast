"""Simple JSON-file config for gh-cast, stored at ~/.config/gh-cast/config.json"""
import json
import os

CONFIG_DIR = os.path.expanduser("~/.config/gh-cast")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def save_config(cfg: dict) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def get_groq_api_key() -> str | None:
    # Priority: env var > config file
    key = os.getenv("GROQ_API_KEY")
    if key:
        return key
    return load_config().get("groq_api_key")


def set_groq_api_key(key: str) -> None:
    cfg = load_config()
    cfg["groq_api_key"] = key
    save_config(cfg)
