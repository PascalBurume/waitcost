"""Optional live web layer for the CityBriefAgent — OFF by default.

The whole project's pitch is "fully offline / reproducible". So this module is a
no-op unless `WAITCOST_ONLINE=1` is set: `fetch`/`search` then return None/[] and
the brief is built purely from the bundled registry + engine data.

When enabled, `fetch` does a plain-stdlib GET (no third-party deps) so a brief can
be refreshed/deepened from a plan URL. Every exception is swallowed → None/[]; this
layer must NEVER raise and must NEVER become a hard dependency. A real search
backend (an MCP tool, or a `requests`-based fetcher) can be wired into `search`
later without changing any caller.
"""
import os
import urllib.request

ONLINE_TIMEOUT = float(os.environ.get("WAITCOST_ONLINE_TIMEOUT", "4"))
_UA = "WaitCost-CityBrief/1.0 (offline-first; live mode opt-in)"


def online_enabled() -> bool:
    """True only when the operator explicitly opted into live mode."""
    return os.environ.get("WAITCOST_ONLINE", "").strip().lower() in ("1", "true", "yes")


def fetch(url):
    """GET `url` and return its text, or None if live mode is off / the fetch fails.

    Never raises — a dead network or a moved link degrades to the offline brief.
    """
    if not online_enabled() or not url:
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=ONLINE_TIMEOUT) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def search(query):
    """Search the web. Returns [{"title","url","snippet"}] or [] when disabled.

    No backend is wired by default (keeps the demo network-free); returns [] so
    the agent silently stays offline. Swap in a real backend here later.
    """
    if not online_enabled() or not query:
        return []
    return []
