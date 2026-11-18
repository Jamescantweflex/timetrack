"""Categories: map (app, domain) -> category name. Applied at query time."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "categories.json"


def load(path: Path | None = None) -> dict:
    with open(path or CONFIG_PATH) as f:
        return json.load(f)


def domain_of(url: str | None) -> str | None:
    if not url:
        return None
    try:
        host = urlsplit(url).hostname
    except ValueError:
        return None
    if not host:
        return None
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _domain_matches(host: str, pattern: str) -> bool:
    return host == pattern or host.endswith("." + pattern)


class Rules:
    def __init__(self, config: dict | None = None):
        cfg = config or load()
        self.browsers = set(cfg.get("browsers", []))
        self.ignore_apps = set(cfg.get("ignore_apps", []))
        self.categories = cfg.get("categories", {})
        self._by_app = {}
        self._by_phone_app = {}
        self._domain_rules = []
        for name, spec in self.categories.items():
            for a in spec.get("apps", []):
                self._by_app[a] = name
            for a in spec.get("phone_apps", []):
                self._by_phone_app[a.lower()] = name
            for d in spec.get("domains", []):
                self._domain_rules.append((d.lower(), name))
        # Longest domain pattern wins (music.youtube.com before youtube.com).
        self._domain_rules.sort(key=lambda r: -len(r[0]))

    def is_browser(self, app: str) -> bool:
        return app in self.browsers

    def is_passive(self, category: str) -> bool:
        return bool(self.categories.get(category, {}).get("passive"))

    def categorise(self, source: str, app: str, domain: str | None) -> str:
        """Return a category name. Falls back to the domain (browser) or app name."""
        if source == "phone":
            return self._by_phone_app.get(app.lower(), app)
        if domain:
            for pattern, name in self._domain_rules:
                if _domain_matches(domain, pattern):
                    return name
            return domain
        return self._by_app.get(app, app)

    def tracked_names(self) -> list[str]:
        return list(self.categories.keys())
