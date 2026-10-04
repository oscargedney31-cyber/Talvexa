from __future__ import annotations

import json
import os
import re
import time
from collections import deque
from html import unescape
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .database import get_db
from .models import Employer, Job


router = APIRouter(
    prefix="/api/global-ingestion",
    tags=["global-ingestion"],
)


USER_AGENT = "TalvexaJobDiscovery/20.0"

MAX_PAGES_PER_EMPLOYER = int(
    os.getenv("TALVEXA_MAX_PAGES_PER_EMPLOYER", "25")
)

REQUEST_TIMEOUT = int(
    os.getenv("TALVEXA_REQUEST_TIMEOUT", "20")
)

CRAWL_DELAY_SECONDS = float(
    os.getenv("TALVEXA_CRAWL_DELAY", "1.5")
)

INGESTION_KEY = os.getenv(
    "TALVEXA_INGESTION_KEY",
    "",
)


session = requests.Session()

session.headers.update(
    {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
    }
)


def require_ingestion_key(
    x_talvexa_ingestion_key: str | None = Header(default=None),
):
    if not INGESTION_KEY:
        raise HTTPException(
            status_code=503,
            detail=(
                "Global ingestion is disabled until "
                "TALVEXA_INGESTION_KEY is configured."
            ),
        )

    if x_talvexa_ingestion_key != INGESTION_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid ingestion key.",
        )

    return True


def clean_text(value) -> str:
    if value is None:
        return ""

    return " ".join(
        unescape(str(value)).split()
    )


def valid_http_url(value: str | None) -> str | None:
    if not value:
        return None

    value = value.strip()

    if not value.startswith(
        (
            "http://",
            "https://",
        )
    ):
        return None

    return value


def normalise_url(url: str) -> str:
    parsed = urlparse(url)

    clean = parsed._replace(
        fragment=""
    )

    return clean.geturl().rstrip("/")


def same_domain(
    first: str,
    second: str,
) -> bool:
    first_host = (
        urlparse(first)
        .netloc
        .lower()
        .split(":")[0]
    )

    second_host = (
        urlparse(second)
        .netloc
        .lower()
        .split(":")[0]
    )

    return first_host == second_host


def looks_like_career_page(url: str) -> bool:
    path = urlparse(url).path.lower()

    keywords = (
        "career",
        "careers",
        "jobs",
        "job",
        "vacancies",
        "vacancy",
        "employment",
        "work-with-us",
        "join-us",
        "join-our-team",
        "opportunities",
    )

    return any(
        keyword in path
        for keyword in keywords
    )


def robots_allowed(url: str) -> bool:
    parsed = urlparse(url)

    robots_url = (
        f"{parsed.scheme}://"
        f"{parsed.netloc}/robots.txt"
    )

    parser = RobotFileParser()

    parser.set_url(robots_url)

    try:
        parser.read()
        return parser.can_fetch(
            USER_AGENT,
            url,
        )
    except Exception:
        return False


def fetch_page(url: str):
    if not robots_allowed(url):
        return None

    try:
        response = session.get(
            url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
    except requests.RequestException:
        return None

    if response.status_code != 200:
        return None

    content_type = (
        response.headers
        .get("content-type", "")
        .lower()
    )

    if "text/html" not in content_type:
        return None

    if len(response.content) > 5 * 1024 * 1024:
        return None

    time.sleep(
        max(
            0,
            CRAWL_DELAY_SECONDS,
        )
    )

    return response.text


def jsonld_objects(
    soup: BeautifulSoup,
) -> list[dict]:
    objects = []

    for script in soup.find_all(
        "script",
        type="application/ld+json",
    ):
        raw = script.string

        if not raw:
            continue

        try:
            data = json.loads(raw)
        except Exception:
            continue

        if isinstance(data, dict):
            objects.append(data)

            graph = data.get("@graph")

            if isinstance(graph, list):
                objects.extend(
                    item
                    for item in graph
                    if isinstance(item, dict)
                )

        elif isinstance(data, list):
            objects.extend(
                item
                for item in data
                if isinstance(item, dict)
            )

    return objects


def schema_types(item: dict) -> set[str]:
    value = item.get("@type")

    if isinstance(value, str):
        return {value.lower()}

    if isinstance(value, list):
        return {
            str(x).lower()
            for x in value
        }

    return set()


def find_job_postings(
    soup: BeautifulSoup,
    page_url: str,
) -> list[dict]:

    jobs = []

    for item in jsonld_objects(soup):

        types = schema_types(item)

        if "jobposting" not in types:
            continue

        title = clean_text(
            item.get("title")
        )

        if not title:
            continue

        description = clean_text(
            item.get("description")
        )

        url = (
            valid_http_url(
                item.get("url")
            )
            or page_url
        )

        location = ""

        job_location = item.get(
            "jobLocation"
        )

        if isinstance(
            job_location,
            dict,
        ):
            address = job_location.get(
                "address"
            )

            if isinstance(
                address,
                dict,
            ):
                location = ", ".join(
                    clean_text(
                        address.get(key)
                    )
                    for key in (
                        "streetAddress",
                        "addressLocality",
                        "addressRegion",
                        "postalCode",
                        "addressCountry",
                    )
                    if clean_text(
                        address.get(key)
                    )
                )

            elif address:
                location = clean_text(
                    address
                )

        elif isinstance(
            job_location,
            list,
        ):
            locations = []

            for location_item in job_location:

                if not isinstance(
                    location_item,
                    dict,
                ):
                    continue

                address = location_item.get(
                    "address"
                )

                if isinstance(
                    address,
                    dict,
                ):
                    text = ", ".join(
                        clean_text(
                            address.get(key)
                        )
                        for key in (
                            "addressLocality",
                            "addressRegion",
                            "addressCountry",
                        )
                        if clean_text(
                            address.get(key)
                        )
                    )

                    if text:
                        locations.append(
                            text
                        )

            location = "; ".join(
                locations
            )

        employment_type = clean_text(
            item.get(
                "employmentType"
            )
        )

        if not employment_type:
            employment_type = "full-time"

        description_lower = (
            description.lower()
        )

        page_text = clean_text(
            soup.get_text(" ")
        ).lower()

        combined = (
            description_lower
            + " "
            + page_text[:5000]
        )

        if "hybrid" in combined:
            work_mode = "hybrid"
        elif (
            "remote" in combined
            or "work from home" in combined
        ):
            work_mode = "remote"
        else:
            work_mode = "onsite"

        salary_min = None
        salary_max = None
        currency = None

        salary = item.get(
            "baseSalary"
        )

        if isinstance(
            salary,
            dict,
        ):
            currency = clean_text(
                salary.get(
                    "currency"
                )
            )

            value = salary.get(
                "value"
            )

            if isinstance(
                value,
                dict,
            ):
                try:
                    salary_min = float(
                        value.get(
                            "minValue"
                        )
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    pass

                try:
                    salary_max = float(
                        value.get(
                            "maxValue"
                        )
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    pass

        identifier = ""

        raw_identifier = item.get(
            "identifier"
        )

        if isinstance(
            raw_identifier,
            dict,
        ):
            identifier = clean_text(
                raw_identifier.get(
                    "value"
                )
            )

        employer_name = ""

        hiring_organization = item.get(
            "hiringOrganization"
        )

        if isinstance(
            hiring_organization,
            dict,
        ):
            employer_name = clean_text(
                hiring_organization.get(
                    "name"
                )
            )

        jobs.append(
            {
                "external_id": identifier,
                "title": title,
                "description": description,
                "location": location,
                "employment_type": employment_type,
                "work_mode": work_mode,
                "salary_min": salary_min,
                "salary_max": salary_max,
                "currency": currency,
                "application_url": url,
                "source_url": page_url,
                "source": "Employer career page",
                "employer_name": employer_name,
            }
        )

    return jobs


def discover_links(
    soup: BeautifulSoup,
    current_url: str,
) -> list[str]:

    links = []

    for anchor in soup.find_all(
        "a",
        href=True,
    ):
        href = anchor.get(
            "href"
        )

        absolute = urljoin(
            current_url,
            href,
        )

        absolute = normalise_url(
            absolute
        )

        parsed = urlparse(
            absolute
        )

        if parsed.scheme not in (
            "http",
            "https",
        ):
            continue

        if not same_domain(
            current_url,
            absolute,
        ):
            continue

        if looks_like_career_page(
            absolute
        ):
            links.append(
                absolute
            )

    return list(
        dict.fromkeys(links)
    )


def get_or_create_employer(
    db: Session,
    name: str,
    website: str,
) -> Employer:

    domain = (
        urlparse(website)
        .netloc
        .lower()
    )

    employer = (
        db.query(Employer)
        .filter(
            Employer.website.ilike(
                f"%{domain}%"
            )
        )
        .first()
    )

    if employer:
        return employer

    employer = Employer(
        name=(
            name
            or domain
            or "Unknown employer"
        ),
        website=website,
        verified=False,
    )

    db.add(employer)
    db.flush()

    return employer


def split_location(
    location: str,
) -> tuple[str | None, str | None]:

    if not location:
        return None, None

    parts = [
        clean_text(x)
        for x in location.split(",")
        if clean_text(x)
    ]

    if not parts:
        return None, None

    if len(parts) == 1:
        return parts[0], None

    return (
        parts[-1],
        parts[0],
    )


def import_job(
    db: Session,
    employer: Employer,
    job_data: dict,
) -> str:

    application_url = (
        job_data.get(
            "application_url"
        )
    )

    existing = None

    if application_url:
        existing = (
            db.query(Job)
            .filter(
                Job.application_url
                == application_url
            )
            .first()
        )

    if existing:
        existing.title = (
            job_data["title"]
        )

        existing.description = (
            job_data["description"]
        )

        existing.source_url = (
            job_data["source_url"]
        )

        existing.source = (
            job_data["source"]
        )

        existing.is_active = True

        return "updated"

    city, country = split_location(
        job_data.get(
            "location",
            "",
        )
    )

    job = Job(
        employer_id=employer.id,
        title=job_data["title"],
        description=(
            job_data["description"]
            or "No description provided."
        ),
        country=country,
        city=city,
        work_mode=(
            job_data["work_mode"]
            or "onsite"
        ),
        employment_type=(
            job_data[
                "employment_type"
            ]
            or "full-time"
        ),
        salary_min=(
            job_data.get(
                "salary_min"
            )
        ),
        salary_max=(
            job_data.get(
                "salary_max"
            )
        ),
        currency=(
            job_data.get(
                "currency"
            )
        ),
        application_url=(
            application_url
        ),
        source=(
            job_data["source"]
        ),
        source_url=(
            job_data["source_url"]
        ),
        work_authorisation=(
            "Check the employer's "
            "requirements before applying."
        ),
        is_active=True,
    )

    db.add(job)

    return "created"


def crawl_employer(
    db: Session,
    website: str,
) -> dict:

    website = normalise_url(
        website
    )

    queue = deque(
        [website]
    )

    visited = set()

    discovered_jobs = []

    while (
        queue
        and len(visited)
        < MAX_PAGES_PER_EMPLOYER
    ):

        url = queue.popleft()

        if url in visited:
            continue

        if not same_domain(
            website,
            url,
        ):
            continue

        visited.add(url)

        html = fetch_page(url)

        if not html:
            continue

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        page_jobs = find_job_postings(
            soup,
            url,
        )

        discovered_jobs.extend(
            page_jobs
        )

        for link in discover_links(
            soup,
            url,
        ):

            if link not in visited:
                queue.append(link)

    employer_name = ""

    for job in discovered_jobs:
        if job.get(
            "employer_name"
        ):
            employer_name = job[
                "employer_name"
            ]
            break

    employer = get_or_create_employer(
        db,
        employer_name,
        website,
    )

    created = 0
    updated = 0

    unique_urls = set()

    for job_data in discovered_jobs:

        application_url = (
            job_data.get(
                "application_url"
            )
        )

        if (
            application_url
            and application_url in unique_urls
        ):
            continue

        if application_url:
            unique_urls.add(
                application_url
            )

        result = import_job(
            db,
            employer,
            job_data,
        )

        if result == "created":
            created += 1
        elif result == "updated":
            updated += 1

    db.commit()

    return {
        "website": website,
        "pages_checked": len(visited),
        "jobs_found": len(
            discovered_jobs
        ),
        "jobs_created": created,
        "jobs_updated": updated,
        "employer": employer.name,
    }


@router.post(
    "/employer",
    dependencies=[
        Depends(require_ingestion_key)
    ],
)
def ingest_employer(
    website: str,
    db: Session = Depends(get_db),
):
    website = website.strip()

    parsed = urlparse(
        website
    )

    if parsed.scheme not in (
        "http",
        "https",
    ):
        raise HTTPException(
            status_code=400,
            detail="Use a valid HTTP or HTTPS employer website.",
        )

    return crawl_employer(
        db,
        website,
    )


@router.post(
    "/batch",
    dependencies=[
        Depends(require_ingestion_key)
    ],
)
def ingest_batch(
    websites: list[str],
    db: Session = Depends(get_db),
):
    if len(websites) > 100:
        raise HTTPException(
            status_code=400,
            detail=(
                "Maximum 100 employer websites "
                "per ingestion batch."
            ),
        )

    results = []

    for website in websites:

        try:
            results.append(
                crawl_employer(
                    db,
                    website.strip(),
                )
            )

        except Exception as exc:
            results.append(
                {
                    "website": website,
                    "error": str(exc),
                }
            )

    return {
        "ok": True,
        "employers_processed": len(
            websites
        ),
        "results": results,
    }
