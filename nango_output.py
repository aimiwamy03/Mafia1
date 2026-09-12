"""
Push a game recap out through Nango once a round ends.

This is intentionally the ONE place Nango shows up in this project - it's an
honest use (pushing a result out to a real tool) rather than forced in
somewhere it doesn't belong.

Setup:
1. In your Nango dashboard, create an integration for Slack (or Google Sheets,
   whichever is faster for your team) and connect your workspace/account -
   this is the OAuth step Nango handles for you.
2. Note your NANGO_SECRET_KEY, NANGO_CONNECTION_ID, and the provider config key
   (e.g. "slack") from that integration.
3. Fill those into your .env file.

The exact proxy endpoint/path depends on which provider you connected - check
nango.dev/docs for the Slack (or Sheets) quickstart, since the request shape
differs per API. This file shows the general pattern: you call Nango's proxy,
it injects your stored credentials and forwards the request.
"""

import os
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

NANGO_SECRET_KEY = os.environ.get("NANGO_SECRET_KEY", "REPLACE_ME")
NANGO_CONNECTION_ID = os.environ.get("NANGO_CONNECTION_ID", "REPLACE_ME")
NANGO_PROVIDER_CONFIG_KEY = os.environ.get("NANGO_PROVIDER_CONFIG_KEY", "slack")
SLACK_CHANNEL = os.environ.get("SLACK_CHANNEL", "#werewolf-recaps")


NANGO_IMAGE_PROVIDER_CONFIG_KEY = os.environ.get("NANGO_IMAGE_PROVIDER_CONFIG_KEY", "openai")
NANGO_IMAGE_CONNECTION_ID = os.environ.get("NANGO_IMAGE_CONNECTION_ID", "")
NANGO_IMAGE_MODEL = os.environ.get("NANGO_IMAGE_MODEL", "dall-e-3")
NANGO_CRYPTO_PROVIDER_CONFIG_KEY = os.environ.get("NANGO_CRYPTO_PROVIDER_CONFIG_KEY", "coingecko")
NANGO_CRYPTO_CONNECTION_ID = os.environ.get("NANGO_CRYPTO_CONNECTION_ID", "")
NANGO_CRYPTO_PATH = os.environ.get(
    "NANGO_CRYPTO_PATH",
    "simple/price?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true",
)


def _nango_ready():
    return NANGO_SECRET_KEY not in ("", "REPLACE_ME") and NANGO_CONNECTION_ID not in ("", "REPLACE_ME")


def _nango_headers(provider=None, connection_id=None):
    return {
        "Authorization": f"Bearer {NANGO_SECRET_KEY}",
        "Connection-Id": connection_id or NANGO_CONNECTION_ID,
        "Provider-Config-Key": provider or NANGO_PROVIDER_CONFIG_KEY,
        "Content-Type": "application/json",
    }


def generate_photo(prompt):
    """Photography Studio — image gen through Nango's OpenAI-compatible proxy."""
    if not _nango_ready():
        raise RuntimeError("Nango is not configured (need NANGO_SECRET_KEY and NANGO_CONNECTION_ID)")
    url = "https://api.nango.dev/proxy/v1/images/generations"
    headers = _nango_headers(
        provider=NANGO_IMAGE_PROVIDER_CONFIG_KEY,
        connection_id=NANGO_IMAGE_CONNECTION_ID or NANGO_CONNECTION_ID,
    )
    payload = {"model": NANGO_IMAGE_MODEL, "prompt": prompt, "n": 1, "size": "1024x1024"}
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    return data["data"][0]["url"]


def send_message(text):
    """Post Office — send a real Slack (or email) message through Nango."""
    if not _nango_ready():
        raise RuntimeError("Nango is not configured (need NANGO_SECRET_KEY and NANGO_CONNECTION_ID)")
    return push_recap_to_slack(
        winner="town dispatch",
        roles_summary=[text],
        model_comparison_note="Sent from the Post Office",
    )


def get_crypto_prices():
    """Bank — return live Bitcoin and Ethereum prices in USD.

    If a CoinGecko Nango connection is configured, the request goes through
    Nango. Otherwise this uses CoinGecko's public endpoint so the Bank still
    works during local rehearsal.
    """
    if _nango_ready() and NANGO_CRYPTO_CONNECTION_ID:
        url = f"https://api.nango.dev/proxy/{NANGO_CRYPTO_PATH.lstrip('/')}"
        headers = _nango_headers(
            provider=NANGO_CRYPTO_PROVIDER_CONFIG_KEY,
            connection_id=NANGO_CRYPTO_CONNECTION_ID,
        )
        response = requests.get(url, headers=headers, timeout=15)
    else:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": "bitcoin,ethereum",
            "vs_currencies": "usd",
            "include_24hr_change": "true",
        }
        response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()
    return {
        "currency": "USD",
        "bitcoin": {
            "usd": data.get("bitcoin", {}).get("usd"),
            "change_24h": data.get("bitcoin", {}).get("usd_24h_change"),
        },
        "ethereum": {
            "usd": data.get("ethereum", {}).get("usd"),
            "change_24h": data.get("ethereum", {}).get("usd_24h_change"),
        },
        "via": "nango" if NANGO_CRYPTO_CONNECTION_ID and _nango_ready() else "coingecko",
    }


def lookup_rate():
    """Backward-compatible name for callers of the original Bank endpoint."""
    return get_crypto_prices()


def push_recap_to_slack(winner, roles_summary, model_comparison_note=""):
    """
    roles_summary: list of "Name: role (AI/human)" strings
    model_comparison_note: e.g. "Gemma-A survived 3 rounds vs Gemma-B's 1"
    """
    text = (
        f"*Werewolf round complete* — winner: *{winner}*\n"
        + "\n".join(roles_summary)
        + (f"\n\n_{model_comparison_note}_" if model_comparison_note else "")
    )

    url = "https://api.nango.dev/proxy/chat.postMessage"
    headers = {
        "Authorization": f"Bearer {NANGO_SECRET_KEY}",
        "Connection-Id": NANGO_CONNECTION_ID,
        "Provider-Config-Key": NANGO_PROVIDER_CONFIG_KEY,
        "Content-Type": "application/json",
    }
    payload = {"channel": SLACK_CHANNEL, "text": text}

    response = requests.post(url, headers=headers, json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    if NANGO_SECRET_KEY == "REPLACE_ME":
        print("Set NANGO_SECRET_KEY, NANGO_CONNECTION_ID as environment variables first.")
    else:
        result = push_recap_to_slack(
            winner="villagers",
            roles_summary=["Alice: detective (human)", "Bob: mafia (AI)"],
            model_comparison_note="Test recap from local run",
        )
        print("Pushed:", result)
