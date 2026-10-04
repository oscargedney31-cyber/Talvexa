from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen


def clean_text(value: Any) -> str:
    if value is None:
        return ""

    return " ".join(str(value).split())


def valid_url(value: Any) -> str | None:
    if not value:
        return None

    value = str(value).strip()

    if value.startswith("https://") or value.startswith("http://"):
        return value

    return None


def fetch_lever_feed(company_slug: str) -> list[dict[str, Any]]:
    """
    Fetch published jobs from a company's public Lever postings feed.

    The company_slug is the public Lever company identifier.
    """

    company_slug = clean_text(company_slug).strip().lower()

    if not company_slug:
        raise ValueError("Company slug is required.")

    encoded_slug = quote(company_slug, safe="")

    url = (
        f"https://api.lever.co/v0/postings/"
        f"{encoded_slug}?mode=json"
    )

    request = Request(
        url,
        headers={
            "User-Agent": "Talvexa/20.1"
        },
    )

    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")

    except Exception as exc:
        raise ValueError(
            f"Unable to retrieve the Lever job feed: {exc}"
        ) from exc

    try:
        data = json.loads(raw)

    except json.JSONDecodeError as exc:
        raise ValueError(
            "The job provider returned invalid JSON."
        ) from exc

    if not isinstance(data, list):
        raise ValueError(
            "The job provider returned an unexpected response."
        )

    jobs = []

    for item in data:

        if not isinstance(item, dict):
            continue

        categories = item.get("categories")

        if not isinstance(categories, dict):
            categories = {}

        title = clean_text(
            item.get("text")
        )

        if not title:
            continue

        description = clean_text(
            item.get("descriptionPlain")
            or item.get("description")
            or ""
        )

        location = clean_text(
            categories.get("location")
        )

        commitment = clean_text(
            categories.get("commitment")
        )

        workplace_type = clean_text(
            item.get("workplaceType")
        ).lower()

        if workplace_type == "remote":
            work_mode = "remote"
        elif workplace_type == "hybrid":
            work_mode = "hybrid"
        else:
            work_mode = "onsite"

        application_url = valid_url(
            item.get("applyUrl")
        )

        source_url = valid_url(
            item.get("hostedUrl")
        )

        jobs.append(
            {
                "external_id": clean_text(
                    item.get("id")
                ),
                "title": title,
                "description": description,
                "location": location,
                "work_mode": work_mode,
                "employment_type": (
                    commitment
                    if commitment
                    else "full-time"
                ),
                "application_url": application_url,
                "source_url": source_url,
                "source": "Lever",
            }
        )

    return jobs
