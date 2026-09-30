import json
import secrets
import sys
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent
CONFIG = BASE / "config.json"
REDIRECT_URI = "http://localhost:8000/callback"
SCOPES = "openid profile w_member_social"


def load_config():
    if not CONFIG.exists():
        raise SystemExit("config.json not found. Copy config.example.json to config.json and fill in your keys.")
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def save_config(cfg):
    CONFIG.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def wait_for_code(auth_url, expected_state):
    result = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != "/callback":
                self.send_response(404)
                self.end_headers()
                return
            params = urllib.parse.parse_qs(parsed.query)
            result.update({k: v[0] for k, v in params.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<h2>Done. You can close this tab and go back to the terminal.</h2>")

        def log_message(self, *args):
            pass

    server = HTTPServer(("localhost", 8000), Handler)
    print("Opening your browser for LinkedIn login...")
    print("If it doesn't open, paste this URL into the browser:\n" + auth_url)
    webbrowser.open(auth_url)
    while "code" not in result and "error" not in result:
        server.handle_request()
    server.server_close()

    if "error" in result:
        raise SystemExit(f"LinkedIn returned an error: {result.get('error')} - {result.get('error_description')}")
    if result.get("state") != expected_state:
        raise SystemExit("State mismatch, aborting for safety. Please try again.")
    return result["code"]


def main():
    cfg = load_config()
    state = secrets.token_urlsafe(16)
    auth_url = "https://www.linkedin.com/oauth/v2/authorization?" + urllib.parse.urlencode({
        "response_type": "code",
        "client_id": cfg["client_id"],
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
    })
    code = wait_for_code(auth_url, state)

    token_resp = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
        },
        timeout=30,
    )
    if not token_resp.ok:
        raise SystemExit(f"Token request failed ({token_resp.status_code}): {token_resp.text}")
    token = token_resp.json()

    me = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {token['access_token']}"},
        timeout=30,
    )
    if not me.ok:
        raise SystemExit(f"Could not read your profile ({me.status_code}): {me.text}")
    info = me.json()

    expires_in = int(token.get("expires_in", 0))
    cfg["access_token"] = token["access_token"]
    cfg["expires_at"] = int(time.time()) + expires_in
    cfg["person_urn"] = f"urn:li:person:{info['sub']}"
    save_config(cfg)
    print(f"Logged in as {info.get('name', '?')}. Token saved, valid for ~{expires_in // 86400} days.")


if __name__ == "__main__":
    main()
