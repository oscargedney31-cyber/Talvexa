from datetime import datetime
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session
from .global_ingestion import router as global_ingestion_router
from .database import Base, engine, get_db
from .matching import match_score
from .models import Employer, Job, JobSeeker
from .schemas import JobCreate, JobOut
from .job_sources import fetch_lever_feed


APP_VERSION = "20.2-job-ingestion"

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Talvexa",
    version=APP_VERSION,
    description="Global AI-powered job discovery and matching platform.",

)
app.include_router(
    global_ingestion_router
)

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "talvexa",
        "version": APP_VERSION,
    }


@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">

<title>Talvexa — Find Me Work</title>

<style>
* {
    box-sizing: border-box;
}

body {
    margin: 0;
    font-family: Inter, system-ui, Arial, sans-serif;
    background: #f5f7fb;
    color: #172033;
}

header {
    background: linear-gradient(135deg, #111827, #243b53);
    color: white;
    padding: 70px 20px;
}

.hero {
    max-width: 1100px;
    margin: auto;
}

.hero h1 {
    font-size: clamp(42px, 7vw, 76px);
    margin: 0 0 15px;
    letter-spacing: -2px;
}

.hero p {
    font-size: 20px;
    max-width: 700px;
    opacity: .9;
}

main {
    max-width: 1100px;
    margin: auto;
    padding: 30px 20px 70px;
}

.card {
    background: white;
    border-radius: 18px;
    padding: 24px;
    margin: 18px 0;
    box-shadow: 0 8px 30px rgba(0,0,0,.07);
}

.search-box {
    margin-top: -45px;
    position: relative;
}

.grid {
    display: grid;
    grid-template-columns: repeat(auto-fit,minmax(200px,1fr));
    gap: 10px;
}

input,
select,
button {
    width: 100%;
    padding: 14px;
    border-radius: 11px;
    border: 1px solid #d0d5dd;
    font-size: 16px;
}

button {
    background: #111827;
    color: white;
    border: 0;
    cursor: pointer;
    font-weight: 700;
}

button:hover {
    opacity: .9;
}

.search-button {
    margin-top: 10px;
}

.job {
    border: 1px solid #e4e7ec;
    border-radius: 14px;
    padding: 20px;
    margin-top: 14px;
}

.job h3 {
    margin-top: 0;
}

.badge {
    display: inline-block;
    background: #eef2ff;
    padding: 6px 10px;
    border-radius: 20px;
    margin: 3px;
    font-size: 13px;
}

.apply {
    display: inline-block;
    margin-top: 12px;
    padding: 12px 18px;
    background: #111827;
    color: white;
    text-decoration: none;
    border-radius: 10px;
    font-weight: 700;
}

.stats {
    display: grid;
    grid-template-columns: repeat(auto-fit,minmax(180px,1fr));
    gap: 12px;
}

.stat {
    background: #f8fafc;
    padding: 18px;
    border-radius: 14px;
}

.stat strong {
    display: block;
    font-size: 28px;
}
</style>
</head>

<body>

<header>
<div class="hero">

<h1>Talvexa</h1>

<p>
Find me work. Search local, remote and international opportunities
from employers and authorised job sources around the world.
</p>

</div>
</header>

<main>

<section class="card search-box">

<h2>Find me work</h2>

<div class="grid">

<input
id="q"
placeholder="Job title, skill or keyword"
/>

<input
id="country"
placeholder="Country"
/>

<select id="mode">

<option value="">
Any work arrangement
</option>

<option value="remote">
Remote
</option>

<option value="hybrid">
Hybrid
</option>

<option value="onsite">
On-site
</option>

</select>

</div>

<button
class="search-button"
onclick="searchJobs()"
>
Search jobs
</button>

</section>


<section class="card">

<h2>Why Talvexa?</h2>

<div class="stats">

<div class="stat">
<strong>🌍</strong>
Global opportunities
</div>

<div class="stat">
<strong>🤖</strong>
AI-powered matching
</div>

<div class="stat">
<strong>💼</strong>
Local & remote work
</div>

<div class="stat">
<strong>✈️</strong>
International opportunities
</div>

</div>

</section>


<section>

<h2>Job opportunities</h2>

<div id="results">

<div class="card">
Search above to find available jobs.
</div>

</div>

</section>

</main>


<script>

async function searchJobs() {

    const params = new URLSearchParams();

    const qValue = document.getElementById("q").value.trim();
    const countryValue = document.getElementById("country").value.trim();
    const modeValue = document.getElementById("mode").value;

    if (qValue) {
        params.set("q", qValue);
    }

    if (countryValue) {
        params.set("country", countryValue);
    }

    if (modeValue) {
        params.set("work_mode", modeValue);
    }

    const results = document.getElementById("results");

    results.innerHTML =
        '<div class="card">Searching...</div>';

    try {

        const response =
            await fetch("/api/jobs?" + params.toString());

        const jobs = await response.json();

        if (!jobs.length) {

            results.innerHTML =
                '<div class="card">No matching jobs found yet.</div>';

            return;
        }

        results.innerHTML = jobs.map(job => {

            const salary =
                job.salary_max
                    ? `<p>Salary: ${esc(job.currency || "")}
                       ${job.salary_min || ""}
                       – ${job.salary_max}</p>`
                    : "";

            const apply =
                job.application_url
                    ? `<a class="apply"
                         href="${attr(job.application_url)}"
                         target="_blank"
                         rel="noopener noreferrer">
                         Apply
                       </a>`
                    : "";

            return `
                <article class="job">

                    <h3>${esc(job.title)}</h3>

                    <p>
                        <span class="badge">
                            ${esc(job.work_mode || "unknown")}
                        </span>

                        <span class="badge">
                            ${esc(job.employment_type || "employment")}
                        </span>
                    </p>

                    <p>
                        📍 ${esc(
                            [job.city, job.country]
                            .filter(Boolean)
                            .join(", ")
                            || "Location not listed"
                        )}
                    </p>

                    <p>
                        ${esc(
                            (job.description || "")
                            .slice(0, 400)
                        )}
                    </p>

                    ${salary}

                    ${apply}

                </article>
            `;

        }).join("");

    } catch (error) {

        results.innerHTML =
            '<div class="card">Unable to search jobs right now.</div>';

    }
}


function esc(value) {

    return String(value ?? "").replace(
        /[&<>"']/g,
        character => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#039;"
        }[character])
    );

}


function attr(value) {

    return String(value ?? "").replace(
        /["<>]/g,
        character => ({
            '"': "&quot;",
            "<": "&lt;",
            ">": "&gt;"
        }[character])
    );

}

</script>

</body>
</html>
"""


@app.get("/api/jobs", response_model=list[JobOut])
def search_jobs(
    q: str | None = Query(default=None),
    country: str | None = Query(default=None),
    work_mode: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):

    query = db.query(Job).filter(
        Job.is_active.is_(True)
    )

    if q:

        term = f"%{q}%"

        query = query.filter(
            or_(
                Job.title.ilike(term),
                Job.description.ilike(term),
                Job.skills.ilike(term),
            )
        )

    if country:

        query = query.filter(
            Job.country.ilike(f"%{country}%")
        )

    if work_mode:

        query = query.filter(
            Job.work_mode.ilike(work_mode)
        )

    return (
        query
        .order_by(Job.created_at.desc())
        .limit(limit)
        .all()
    )


@app.post("/api/jobs", response_model=JobOut)
def create_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
):

    if not db.get(
        Employer,
        payload.employer_id
    ):

        raise HTTPException(
            status_code=404,
            detail="Employer not found",
        )

    job = Job(
        **payload.model_dump(),
        verified_at=datetime.utcnow(),
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    return job


@app.get("/api/jobs/{job_id}", response_model=JobOut)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
):

    job = db.get(Job, job_id)

    if not job:

        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    return job


@app.get("/api/jobs/{job_id}/match/{seeker_id}")
def get_match(
    job_id: int,
    seeker_id: int,
    db: Session = Depends(get_db),
):

    job = db.get(Job, job_id)
    seeker = db.get(JobSeeker, seeker_id)

    if not job or not seeker:

        raise HTTPException(
            status_code=404,
            detail="Job or seeker not found",
        )

    return {
        "job_id": job.id,
        "seeker_id": seeker.id,
        "match_score": match_score(
            seeker,
            job,
        ),
    }


@app.get("/api/ingestion/status")
def ingestion_status():

    return {
        "status": "ready",
        "version": APP_VERSION,
        "service": "Talvexa job ingestion",
        "supported_sources": [
            "Employer career pages",
            "Authorised APIs",
            "Licensed job feeds",
            "Direct employer submissions",
            "Lever public postings",
        ],
    }


@app.post("/api/ingestion/lever/{company_slug}")
def import_lever_jobs(
    company_slug: str,
    db: Session = Depends(get_db),
):

    try:

        jobs = fetch_lever_feed(
            company_slug
        )

    except Exception as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    employer_url = (
        f"https://jobs.lever.co/{company_slug}"
    )

    employer = (
        db.query(Employer)
        .filter(
            Employer.website == employer_url
        )
        .first()
    )

    if not employer:

        employer = Employer(
            name=company_slug,
            website=employer_url,
            verified=False,
            created_at=datetime.utcnow(),
        )

        db.add(employer)
        db.flush()

    imported = 0
    skipped = 0

    for item in jobs:

        application_url = item.get(
            "application_url"
        )

        if not application_url:

            skipped += 1
            continue

        existing = (
            db.query(Job)
            .filter(
                Job.application_url
                == application_url
            )
            .first()
        )

        if existing:

            skipped += 1
            continue

        job = Job(
            employer_id=employer.id,
            title=item["title"],
            description=item["description"],
            country=None,
            city=item.get("location"),
            address=None,
            work_mode=item.get(
                "work_mode",
                "onsite",
            ),
            employment_type=item.get(
                "employment_type",
                "full-time",
            ),
            salary_min=None,
            salary_max=None,
            currency=None,
            skills="",
            qualifications="",
            work_authorisation=(
                "Check the employer's "
                "requirements before applying."
            ),
            application_url=application_url,
            source=item.get(
                "source",
                "Lever",
            ),
            source_url=item.get(
                "source_url"
            ),
            is_active=True,
            verified_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )

        db.add(job)

        imported += 1

    db.commit()

    return {
        "ok": True,
        "company": company_slug,
        "found": len(jobs),
        "imported": imported,
        "skipped": skipped,
    }
