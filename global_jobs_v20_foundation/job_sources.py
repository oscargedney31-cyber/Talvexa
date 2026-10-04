from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import requests


def clean_text(value: Any) -> str:
    if value is None:
        return ""

    return " ".join(str(value).split())


def parse_location(location: str) -> tuple[str, str]:
    location = clean_text(location)

    if not location:
        return "", ""

    parts = [part.strip() for part in location.split(",") if part.strip()]

    if len(parts) == 1:
        return parts[0], ""

    return parts[0], parts[-1]


def valid_http_url(value: Any) -> str | None:
    if not value:
        return None

    value = str(value).strip()

    parsed = urlparse(value)

    if parsed.scheme not in {"http", "https"}:
        return None

    if not parsed.netloc:
        return None

    return value


def fetch_lever_feed(
    company_slug: str,
) -> list[dict[str, Any]]:

    company_slug = clean_text(company_slug).lower()

    if not company_slug:
        raise ValueError("Lever company slug is required.")

    url = (
        "https://api.lever.co/v0/postings/"
        f"{company_slug}"
        "?mode=json"
    )

    response = requests.get(
        url,
        timeout=20,
        headers={
            "User-Agent": "Talvexa/20.1"
        },
    )

    response.raise_for_status()

    data = response.json()

    if not isinstance(data, list):
        raise ValueError(
            "Lever returned an unexpected response."
        )

    jobs: list[dict[str, Any]] = []

    for item in data:

        if not isinstance(item, dict):
            continue

        title = clean_text(
            item.get("text")
            or item.get("position")
        )

        if not title:
            continue

        location = clean_text(
            item.get("categories", {}).get("location")
            if isinstance(item.get("categories"), dict)
            else item.get("location")
        )

        city, country = parse_location(location)

        apply_url = valid_http_url(
            item.get("applyUrl")
            or item.get("apply_url")
        )

        posting_url = valid_http_url(
            item.get("hostedUrl")
            or item.get("url")
        )

        commitment = clean_text(
            item.get("categories", {}).get("commitment")
            if isinstance(item.get("categories"), dict)
            else item.get("commitment")
        )

        workplace_type = clean_text(
            item.get("workplaceType")
        ).lower()

        if workplace_type not in {
            "remote",
            "hybrid",
            "onsite",
        }:
            workplace_type = "onsite"

        jobs.append(
            {
                "external_id": clean_text(
                    item.get("id")
                ),
                "title": title,
                "description": clean_text(
                    item.get("description")
                ),
                "city": city,
                "country": country,
                "work_mode": workplace_type,
                "employment_type": (
                    commitment or "full-time"
                ),
                "application_url": apply_url,
                "source_url": posting_url,
                "source": "Lever",
            }
        )

    return jobs
