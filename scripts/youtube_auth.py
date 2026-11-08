"""One-time YouTube OAuth consent for the livestream channel. Run it yourself in a terminal:

    /home/andyshi2/.conda/envs/ai-livestream/bin/python scripts/youtube_auth.py

1. It prints a Google link. Open it in your browser and approve with the channel's Google account.
2. Google then sends your browser to http://localhost:8765/?... , which will NOT load (that is expected:
   localhost here is your laptop, not this machine). Copy the whole address from the address bar.
3. Paste it back here and press Enter. The refresh token is saved to secrets/youtube_token.json (mode 600);
   every later run reuses it, so you only do this once.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: E402

from broadcast import youtube  # noqa: E402


def main() -> int:
    os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")   # Google may return the scopes in a different order/superset
    flow = InstalledAppFlow.from_client_secrets_file(str(youtube.client_secret_path()), scopes=youtube.SCOPES,
                                                     redirect_uri="http://localhost:8765/")
    url, _ = flow.authorization_url(access_type="offline", prompt="consent", include_granted_scopes="true")
    print("\n1) Open this link and approve:\n\n" + url + "\n")
    reply = input("2) Paste the full http://localhost:8765/... address your browser ended up on:\n> ").strip()
    if "code=" not in reply:
        print("That does not contain ?code=... ; run the script again and paste the whole address.")
        return 1
    flow.fetch_token(authorization_response=reply.replace("http://", "https://", 1) if reply.startswith("http://localhost") else reply)
    youtube.save_token(flow.credentials)
    ch = youtube.channel()
    print(f"\nAuthorised. Channel: {ch.get('snippet', {}).get('title', '?')}  (token saved to {youtube.TOKEN_PATH})")
    live = ch.get("status", {}).get("longUploadsStatus")
    print("Long uploads / live status:", live or "unknown")
    return 0


if __name__ == "__main__":
    sys.exit(main())
