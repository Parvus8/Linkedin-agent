"""Publishes the oldest post in queue/approved to LinkedIn, with its image if there is one.
An image is any .png/.jpg/.jpeg with the same name as the post's .md file.
Usage: python publish.py [--dry-run]"""
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
API = "https://api.linkedin.com/rest"
IMAGE_EXTS = (".png", ".jpg", ".jpeg")

# None = auto-detect: tries the current month, then goes back month by month
# until LinkedIn accepts one. To pin a version, set e.g. LINKEDIN_VERSION = "202608".
LINKEDIN_VERSION = None
WARN_DAYS = 7


def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] {msg}")


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


def to_little_text(text):
    # LinkedIn's "commentary" field treats these characters as markup, so escape them all...
    escaped = re.sub(r"([\\|{}@\[\]()<>#*_~])", r"\\\1", text)
    # ...then turn #word back into real, clickable hashtags.
    return re.sub(r"\\#(\w+)", r"{hashtag|\\#|\1}", escaped)


class LinkedIn:
    def __init__(self, token):
        self.token = token
        self.version = None  # remembered after the first call that works

    def post(self, path, body):
        versions = [self.version] if self.version else candidate_versions()
        for version in versions:
            resp = requests.post(
                API + path,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "LinkedIn-Version": version,
                    "X-Restli-Protocol-Version": "2.0.0",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=60,
            )
            # 426 = version not active; the request was rejected, so trying again is safe.
            if resp.status_code == 426 and "NONEXISTENT_VERSION" in resp.text:
                continue
            self.version = version
            return resp
        return resp

    def upload_image(self, owner, path):
        init = self.post("/images?action=initializeUpload", {"initializeUploadRequest": {"owner": owner}})
        if not init.ok:
            raise SystemExit(f"Image upload init failed ({init.status_code}): {init.text}")
        value = init.json()["value"]
        up = requests.put(
            value["uploadUrl"],
            data=path.read_bytes(),
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/octet-stream"},
            timeout=120,
        )
        if up.status_code not in (200, 201):
            raise SystemExit(f"Image upload failed ({up.status_code}): {up.text}")
        return value["image"]


def find_image(draft):
    for ext in IMAGE_EXTS:
        candidate = draft.with_suffix(ext)
        if candidate.exists():
            return candidate
    return None


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
    image = find_image(draft)

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
        log(f"DRY RUN - would publish {draft.name}"
            f" with image {image.name if image else '(none)'}:\n\n{body['commentary']}")
        return

    li = LinkedIn(cfg["access_token"])
    if image:
        image_urn = li.upload_image(cfg["person_urn"], image)
        body["content"] = {"media": {"id": image_urn, "altText": text.split("\n")[0][:300]}}

    resp = li.post("/posts", body)
    if resp.status_code != 201:
        raise SystemExit(f"Publish failed ({resp.status_code}): {resp.text}")

    post_id = resp.headers.get("x-restli-id", "?")
    POSTED.mkdir(parents=True, exist_ok=True)
    shutil.move(str(draft), str(POSTED / draft.name))
    if image:
        shutil.move(str(image), str(POSTED / image.name))
    with HISTORY.open("a", encoding="utf-8") as h:
        h.write(f"\n\n## {datetime.now():%Y-%m-%d %H:%M} ({post_id})\n{text}\n")
    log(f"Published {draft.name}{' + ' + image.name if image else ''} -> {post_id} (API version {li.version})")


if __name__ == "__main__":
    main()
