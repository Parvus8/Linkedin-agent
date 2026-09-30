"""Generates LinkedIn post drafts (text + optional illustration) with Claude Code into queue/pending.
Usage: python generate.py [number_of_posts]"""
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from images import render

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent
GUIDELINES = BASE / "guidelines.md"
HISTORY = BASE / "history.md"
PENDING = BASE / "queue" / "pending"
APPROVED = BASE / "queue" / "approved"

INSTRUCTION = "Write one new LinkedIn post following the guidelines and output format provided on stdin."
HISTORY_CHARS = 8000  # how much recent history Claude sees, to avoid repeating itself
SEPARATOR = "===IMAGE==="

OUTPUT_FORMAT = f"""# OUTPUT FORMAT
First, the final post text: no title, no preamble, no explanations, no markdown, no surrounding quotes.
Then a line containing exactly {SEPARATOR}
Then ONE JSON object (no code fences) describing the illustration for the post:
- Code example: {{"type": "code", "language": "sql", "title": "short title", "code": "..."}}
  Max 15 lines, max 60 characters per line. Language is a Pygments name (sql, python, bash, yaml...).
- Summary card: {{"type": "card", "title": "short title", "points": ["...", "..."]}}
  2 to 4 points, each under 90 characters.
- No image: {{"type": "none"}}
Prefer "code" when the post teaches something technical, "card" for concepts, tips and career posts.
The image text must be in the same language as the post. No emojis in the image."""


def read(path):
    return path.read_text(encoding="utf-8") if path.exists() else ""


def queued_posts():
    files = sorted(PENDING.glob("*.md")) + sorted(APPROVED.glob("*.md"))
    return "\n\n---\n\n".join(read(f) for f in files)


def build_context():
    history = read(HISTORY)[-HISTORY_CHARS:]
    return (
        "# GUIDELINES\n" + read(GUIDELINES)
        + "\n\n# ALREADY PUBLISHED (do not repeat these topics or angles)\n" + (history or "(none yet)")
        + "\n\n# ALREADY QUEUED (do not repeat these either)\n" + (queued_posts() or "(none)")
        + "\n\n" + OUTPUT_FORMAT
    )


def run_claude(context):
    exe = shutil.which("claude")
    if not exe:
        raise SystemExit("Could not find 'claude' on PATH. Check that 'claude --version' works in cmd.")
    result = subprocess.run(
        [exe, "-p", INSTRUCTION],
        input=context,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
        cwd=BASE,
    )
    if result.returncode != 0:
        raise SystemExit(f"Claude Code failed:\n{result.stderr}")
    return result.stdout.strip()


def parse_output(raw):
    if SEPARATOR not in raw:
        return raw.strip(), None
    text, spec_raw = raw.split(SEPARATOR, 1)
    spec_raw = spec_raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        spec = json.loads(spec_raw)
    except json.JSONDecodeError:
        print("Could not parse the image description, saving the post without an image.")
        spec = None
    return text.strip(), spec


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    PENDING.mkdir(parents=True, exist_ok=True)
    APPROVED.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        text, spec = parse_output(run_claude(build_context()))
        if not text:
            print("Empty response from Claude, skipping.")
            continue
        stem = datetime.now().strftime("%Y%m%d-%H%M%S") + f"-{i + 1:02d}"
        (PENDING / f"{stem}.md").write_text(text + "\n", encoding="utf-8")
        image_note = ""
        try:
            if render(spec, PENDING / f"{stem}.png"):
                image_note = f" + {stem}.png"
        except Exception as e:
            print(f"Image rendering failed ({e}), saving the post without an image.")
        print(f"[{datetime.now():%Y-%m-%d %H:%M}] Draft saved: queue/pending/{stem}.md{image_note}")


if __name__ == "__main__":
    main()
