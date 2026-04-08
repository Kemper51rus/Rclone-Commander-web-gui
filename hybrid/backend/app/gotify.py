from __future__ import annotations

import json
import logging
from urllib import error, request

from .domain import GotifySettings


logger = logging.getLogger(__name__)


class GotifyClient:
    def send(self, settings: GotifySettings, *, title: str, message: str, priority: int) -> bool:
        normalized = settings.normalized()
        if not normalized.is_configured():
            return False

        url = normalized.url.rstrip("/") + f"/message?token={normalized.token}"
        payload = json.dumps(
            {
                "title": title,
                "message": message,
                "priority": min(10, max(1, int(priority))),
            }
        ).encode("utf-8")
        req = request.Request(
            url,
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        try:
            with request.urlopen(req, timeout=8) as response:
                return 200 <= int(response.status) < 300
        except (error.URLError, TimeoutError, ValueError) as exc:
            logger.warning("gotify notification failed: %s", exc)
            return False
