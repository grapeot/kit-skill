from __future__ import annotations

from typing import Any

import requests


class KitClient:
    def __init__(self, api_key: str, base_url: str, timeout: int = 30) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Kit-Api-Key": self.api_key,
        }

    def create_broadcast(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/broadcasts",
            headers=self._headers(),
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        if not response.text.strip():
            return {}
        return response.json().get("broadcast", response.json())

    def list_tags(self, per_page: int = 1000) -> dict[str, Any]:
        response = requests.get(
            f"{self.base_url}/tags",
            headers=self._headers(),
            params={"per_page": per_page},
            timeout=self.timeout,
        )
        response.raise_for_status()
        if not response.text.strip():
            return {}
        return response.json()

    def broadcast_stats(self, broadcast_id: int | str) -> dict[str, Any]:
        response = requests.get(
            f"{self.base_url}/broadcasts/{broadcast_id}/stats",
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        if not response.text.strip():
            return {}
        return response.json()
