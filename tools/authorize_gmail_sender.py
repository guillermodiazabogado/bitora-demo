"""Authorize a Gmail sender locally and provision Railway without logging secrets."""
import argparse
import json
from pathlib import Path
import secrets
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.services.email import GmailEmailProvider
from backend.services.google_oauth import GoogleOAuthClient, GoogleOAuthConfig


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--runtime-dir", required=True)
    parser.add_argument("--railway", required=True)
    parser.add_argument("--sender", required=True)
    args = parser.parse_args()
    values = {}
    for line in Path(args.env_file).read_text(encoding="utf-8-sig").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"").strip("'")
    config = GoogleOAuthConfig(
        enabled=True, client_id=values["GOOGLE_OAUTH_CLIENT_ID"],
        client_secret=values["GOOGLE_OAUTH_CLIENT_SECRET"],
        redirect_uri=values["GOOGLE_OAUTH_REDIRECT_URI"],
        scopes="openid email https://www.googleapis.com/auth/gmail.send",
    )
    callback = urlparse(config.redirect_uri)
    if callback.hostname not in {"localhost", "127.0.0.1"}:
        raise ValueError("A loopback callback is required")
    runtime = Path(args.runtime_dir)
    runtime.mkdir(parents=True, exist_ok=True)
    state = secrets.token_urlsafe(32)
    client = GoogleOAuthClient(config)
    finished = False

    def status(value):
        (runtime / "status.json").write_text(json.dumps(value), encoding="utf-8")

    def railway_value(key, value):
        result = subprocess.run(
            [args.railway, "variable", "set", key, "--stdin", "-s", "web", "--skip-deploys"],
            input=value, text=True, capture_output=True,
        )
        if result.returncode:
            raise RuntimeError("Railway could not save configuration")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            nonlocal finished
            query = parse_qs(urlparse(self.path).query)
            if urlparse(self.path).path != callback.path:
                self.send_error(404)
                return
            if not secrets.compare_digest(query.get("state", [""])[0], state):
                self.send_error(403)
                return
            try:
                tokens = client.exchange_code(query.get("code", [""])[0])
                account = client.userinfo(tokens["access_token"])
                if account.get("email", "").lower() != args.sender.lower():
                    raise RuntimeError("Authorize the configured sender account")
                refresh = tokens.get("refresh_token")
                if not refresh or "https://www.googleapis.com/auth/gmail.send" not in tokens.get("scope", "").split():
                    raise RuntimeError("Gmail send permission or refresh token missing")
                provider = GmailEmailProvider(
                    client_id=config.client_id, client_secret=config.client_secret,
                    refresh_token=refresh, from_email=f"BITORA <{args.sender}>", reply_to=args.sender,
                )
                sent = provider.send_email(to=args.sender, subject="BITORA - Gmail conectado",
                                           html="<p>La cuenta Gmail quedo autorizada para enviar confirmaciones de BITORA.</p>")
                if not sent.ok:
                    raise RuntimeError(sent.error)
                for key, value in {
                    "GMAIL_CLIENT_ID": config.client_id, "GMAIL_CLIENT_SECRET": config.client_secret,
                    "GMAIL_REFRESH_TOKEN": refresh, "EMAIL_FROM": f"BITORA <{args.sender}>",
                    "EMAIL_REPLY_TO": args.sender, "EMAIL_PROVIDER": "gmail",
                }.items():
                    railway_value(key, value)
                deploy = subprocess.run([args.railway, "redeploy", "-s", "web", "-y"], capture_output=True)
                if deploy.returncode:
                    raise RuntimeError("Configuration saved; deployment still required")
                status({"status": "configured", "sender": args.sender, "test_message_id": sent.message_id})
                message = "Gmail conectado. Podes volver al chat de BITORA."
            except Exception as exc:
                status({"status": "error", "reason": type(exc).__name__})
                message = "La conexion no se completo. Volve al chat para revisar el siguiente paso."
            body = message.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            finished = True

    with HTTPServer(("127.0.0.1", callback.port or 80), Handler) as httpd:
        httpd.timeout = 1
        (runtime / "authorization-url.txt").write_text(
            client.authorization_url(state=state, login_hint=args.sender), encoding="utf-8",
        )
        status({"status": "waiting_for_google", "sender": args.sender})
        deadline = time.monotonic() + 1800
        while not finished and time.monotonic() < deadline:
            httpd.handle_request()
        if not finished:
            status({"status": "expired"})


if __name__ == "__main__":
    main()
