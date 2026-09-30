"""Usage: python generate.py [number_of_posts]"""
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent
GUIDELINES = BASE / "guidelines.md"
HISTORY = BASE / "history.md"
PENDING = BASE / "queue" / "pending"
APPROVED = BASE / "queue" / "approved"

INSTRUCTION = "Write one new LinkedIn post following the guidelines provided on stdin. Output only the post text."
HISTORY_CHARS = 8000


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
        + "\n\n# TASK\nWrite ONE new post. Output only the final post text: no title, no preamble, "
          "no explanations, no markdown formatting, no surrounding quotes."
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


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    PENDING.mkdir(parents=True, exist_ok=True)
    APPROVED.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        post = run_claude(build_context())
        if not post:
            print("Empty response from Claude, skipping.")
            continue
        name = datetime.now().strftime("%Y%m%d-%H%M%S") + f"-{i + 1:02d}.md"
        (PENDING / name).write_text(post + "\n", encoding="utf-8")
        print(f"[{datetime.now():%Y-%m-%d %H:%M}] Draft saved: queue/pending/{name}")


if __name__ == "__main__":
    main()
