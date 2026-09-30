"""Usage: python publish.py [--dry-run]"""
import json
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent
CONFIG = BASE / "config.json"
HISTORY = BASE / "history.md"
APPROVED = BASE / "queue" / "approved"
POSTED = BASE / "queue" / "posted"

LINKEDIN_VERSION = None
WARN_DAYS = 7


def candidate_versions():
    if LINKEDIN_VERSION:
        return [LINKEDIN_VERSION]
    now = datetime.now()
    year, month = now.year, now.month
    versions = []
    for _ in range(12):
        versions.append(f"{year}{month:02d}")
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return versions


def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] {msg}")


def to_little_text(text):
    escaped = re.sub(r"([\\|{}@\[\]()<>#*_~])", r"\\\1", text)
    return re.sub(r"\\#(\w+)", r"{hashtag|\\#|\1}", escaped)


def main():
    dry_run = "--dry-run" in sys.argv
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))

    if not cfg.get("access_token") or not cfg.get("person_urn"):
        raise SystemExit("Not logged in. Run: python auth.py")
    days_left = (cfg.get("expires_at", 0) - time.time()) / 86400
    if days_left <= 0:
        raise SystemExit("LinkedIn token expired. Run: python auth.py")
    if days_left < WARN_DAYS:
        log(f"WARNING: LinkedIn token expires in {days_left:.0f} days. Run python auth.py soon.")

    APPROVED.mkdir(parents=True, exist_ok=True)
    drafts = sorted(APPROVED.glob("*.md"))
    if not drafts:
        log("No approved posts in queue/approved. Nothing to publish.")
        return
    draft = drafts[0]
    text = draft.read_text(encoding="utf-8").strip()

    body = {
        "author": cfg["person_urn"],
        "commentary": to_little_text(text),
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }

    if dry_run:
        log(f"DRY RUN - would publish {draft.name}:\n\n{body['commentary']}")
        return

    for version in candidate_versions():
        resp = requests.post(
            "https://api.linkedin.com/rest/posts",
            headers={
                "Authorization": f"Bearer {cfg['access_token']}",
                "LinkedIn-Version": version,
                "X-Restli-Protocol-Version": "2.0.0",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=30,
        )
        if resp.status_code == 426 and "NONEXISTENT_VERSION" in resp.text:
            continue
        break
    if resp.status_code != 201:
        raise SystemExit(f"Publish failed ({resp.status_code}): {resp.text}")

    post_id = resp.headers.get("x-restli-id", "?")
    POSTED.mkdir(parents=True, exist_ok=True)
    shutil.move(str(draft), str(POSTED / draft.name))
    with HISTORY.open("a", encoding="utf-8") as h:
        h.write(f"\n\n## {datetime.now():%Y-%m-%d %H:%M} ({post_id})\n{text}\n")
    log(f"Published {draft.name} -> {post_id} (API version {version})")


if __name__ == "__main__":
    main()
