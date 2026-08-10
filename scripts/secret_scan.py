from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SKIP_DIRS = {
    ".git",
    ".agents",
    ".codex",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    "output",
    "backups",
    "backup",
    "storage",
    "tmp",
    "deploy_package",
}

SKIP_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".dump",
    ".sqlite3",
    ".pyc",
}

SKIP_NAMES = {
    ".env",
    ".env.staging",
    "html5-qrcode.min.js",
}

PATTERNS = [
    re.compile(r"EA[A-Za-z0-9_-]{40,}"),
    re.compile(r"GOCSPX-[A-Za-z0-9_-]{20,}"),
    re.compile(r"re_[A-Za-z0-9]{20,}"),
]

ASSIGNMENT_KEYS = (
    "WHATSAPP_ACCESS_TOKEN",
    "WHATSAPP_APP_SECRET",
    "META_APP_SECRET",
    "GOOGLE_CLIENT_SECRET",
    "GOOGLE_OAUTH_CLIENT_SECRET",
    "CLIENT_SECRET",
    "APP_SECRET",
)

PLACEHOLDERS = {
    "",
    "...",
    "<token>",
    "<token_meta>",
    "<app_secret>",
    "<valor local>",
    "<valor>",
    "changeme",
    "change_me",
    "example",
}


def is_skipped(path: Path) -> bool:
    rel_parts = path.relative_to(ROOT).parts
    if any(part in SKIP_DIRS for part in rel_parts):
        return True
    if path.name in SKIP_NAMES:
        return True
    return path.suffix.lower() in SKIP_SUFFIXES


def read_text(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return data.decode("latin-1")
        except UnicodeDecodeError:
            return None


def is_placeholder(value: str) -> bool:
    cleaned = value.strip().strip('"').strip("'")
    if cleaned in PLACEHOLDERS:
        return True
    if cleaned.startswith("$"):
        return True
    return cleaned.startswith("<") and cleaned.endswith(">")


def scan() -> list[str]:
    findings: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or is_skipped(path):
            continue
        text = read_text(path)
        if text is None:
            continue
        rel = path.relative_to(ROOT)
        for index, line in enumerate(text.splitlines(), start=1):
            for pattern in PATTERNS:
                if pattern.search(line):
                    findings.append(f"{rel}:{index}: token pattern")
            for key in ASSIGNMENT_KEYS:
                match = re.search(rf"\b{re.escape(key)}\s*=\s*(.+)", line)
                if match and not is_placeholder(match.group(1)):
                    findings.append(f"{rel}:{index}: sensitive assignment {key}")
    return findings


if __name__ == "__main__":
    results = scan()
    if results:
        print("Secret scan failed:")
        for result in results:
            print(result)
        sys.exit(1)
    print("Secret scan passed.")
