"""Cookie-based authentication."""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Session:
    """Authenticated session."""

    cookies: dict[str, str]

    def get_cookie_header(self) -> str:
        """Format cookies for HTTP header."""
        return "; ".join(f"{k}={v}" for k, v in self.cookies.items())


def load_cookies(cookie_file: Path) -> Session:
    """Load session from a JSON cookie file."""
    data = json.loads(cookie_file.read_text())

    if isinstance(data, dict):
        cookies = data
    elif isinstance(data, list):
        cookies = {c["name"]: c["value"] for c in data if "name" in c}
    else:
        raise ValueError("Invalid cookie file format")

    if "orm-jwt" not in cookies and "ezproxy" not in cookies and "ezproxyn" not in cookies:
        raise ValueError("Missing orm-jwt or ezproxy cookie - are you logged into O'Reilly?")

    return Session(cookies=cookies)
