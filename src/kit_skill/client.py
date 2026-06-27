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

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = requests.get(
            f"{self.base_url}{path}",
            headers=self._headers(),
            params=params,
            timeout=self.timeout,
        )
        if response.status_code == 429:
            raise requests.HTTPError(
                "Rate limit exceeded (120 req/60s). Please wait before retrying.",
                response=response,
            )
        response.raise_for_status()
        if not response.text.strip():
            return {}
        return response.json()

    def _post(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        response = requests.post(
            f"{self.base_url}{path}",
            headers=self._headers(),
            json=payload or {},
            timeout=self.timeout,
        )
        if response.status_code == 429:
            raise requests.HTTPError(
                "Rate limit exceeded (120 req/60s). Please wait before retrying.",
                response=response,
            )
        response.raise_for_status()
        if not response.text.strip():
            return {}
        return response.json()

    def create_broadcast(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = self._post("/broadcasts", payload=payload)
        return data.get("broadcast", data)

    def list_tags(self, per_page: int = 1000) -> dict[str, Any]:
        return self._get("/tags", params={"per_page": per_page})

    def broadcast_stats(self, broadcast_id: int | str) -> dict[str, Any]:
        return self._get(f"/broadcasts/{broadcast_id}/stats")

    def account(self) -> dict[str, Any]:
        return self._get("/account")

    def growth_stats(self, start_date: str, end_date: str) -> dict[str, Any]:
        return self._get("/account/growth_stats", params={"starting": start_date, "ending": end_date})

    def email_stats(self) -> dict[str, Any]:
        return self._get("/account/email_stats")

    def subscribers(self, status: str = "active", per_page: int = 50) -> dict[str, Any]:
        return self._get(
            "/subscribers",
            params={"status": status, "include_total_count": "true", "per_page": per_page},
        )

    def subscriber_count(self, status: str = "active") -> int:
        data = self.subscribers(status=status, per_page=1)
        pagination = data.get("pagination") or data.get("meta") or {}
        total = pagination.get("total_count") or data.get("total_subscribers") or data.get("total")
        if total is not None:
            return int(total)
        return len(data.get("subscribers", []))

    def broadcasts(self, per_page: int = 10) -> dict[str, Any]:
        return self._get("/broadcasts", params={"per_page": per_page, "sort_order": "desc"})

    def sequences(self, per_page: int = 50) -> dict[str, Any]:
        return self._get("/sequences", params={"per_page": per_page})

    def sequence(self, sequence_id: int | str) -> dict[str, Any]:
        data = self._get(f"/sequences/{sequence_id}")
        return data.get("sequence", data)

    def sequence_subscribers(
        self, sequence_id: int | str, status: str = "active", per_page: int = 50
    ) -> dict[str, Any]:
        return self._get(
            f"/sequences/{sequence_id}/subscribers",
            params={"status": status, "include_total_count": "true", "per_page": per_page},
        )

    def sequence_subscriber_count(self, sequence_id: int | str) -> int:
        sequence = self.sequence(sequence_id)
        count = sequence.get("subscriber_count")
        return int(count) if count is not None else 0

    def create_subscriber(self, email_address: str) -> dict[str, Any]:
        return self._post("/subscribers", payload={"email_address": email_address})

    def add_subscriber_to_sequence(self, sequence_id: int | str, email_address: str) -> dict[str, Any]:
        return self._post(
            f"/sequences/{sequence_id}/subscribers",
            payload={"email_address": email_address},
        )

    def snapshot(self, start_date: str, end_date: str, broadcasts_limit: int = 10) -> dict[str, Any]:
        data: dict[str, Any] = {
            "start_date": start_date,
            "end_date": end_date,
            "growth_stats": self.growth_stats(start_date, end_date),
            "email_stats": self.email_stats(),
        }
        broadcasts = self.broadcasts(per_page=broadcasts_limit).get("broadcasts", [])
        enriched: list[dict[str, Any]] = []
        for broadcast in broadcasts:
            broadcast_id = broadcast.get("id")
            entry = {
                "id": broadcast_id,
                "subject": broadcast.get("subject"),
                "published_at": broadcast.get("published_at"),
                "recipients": broadcast.get("recipients"),
            }
            if broadcast_id:
                try:
                    entry["stats"] = self.broadcast_stats(broadcast_id)
                except requests.HTTPError:
                    entry["stats"] = None
            enriched.append(entry)
        data["recent_broadcasts"] = enriched
        return data
