from datetime import datetime
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .matching import match_score
from .models import Employer, Job, JobSeeker
from .schemas import JobCreate, JobOut
from .job_sources import fetch_lever_feed
Base.metadata.create_all(bind=engine)

APP_VERSION = "20.1-job-ingestion"

app = FastAPI(
    title="Talvexa",
    version=APP_VERSION,
    description="AI-first global employment and job-matching platform.",
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
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Talvexa — Find your next opportunity</title>
<style>
*{box-sizing:border-box}
body{
    margin:0;
    font-family:system-ui,sans-serif;
    background:#f5f7fb;
    color:#172033
}
header{
    background:#101828;
    color:white;
    padding:42px 20px
}
main{
    max-width:1100px;
    margin:auto;
    padding:24px
}
.card{
    background:white;
    border-radius:16px;
    padding:22px;
    margin:14px 0;
    box-shadow:0 4px 18px rgba(0,0,0,.06)
}
.grid{
    display:grid;
    grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
    gap:8px
}
input,select,button{
    width:100%;
    padding:12px;
    border:1px solid #d0d5dd;
    border-radius:10px;
    margin:4px 0
}
button{
    cursor:pointer;
    background:#101828;
    color:white;
    border:0
}
a{text-decoration:none}
</style>
</head>

<body>

<header>
<main>
<h1>Talvexa</h1>
<p>Find your next opportunity — locally, remotely or internationally.</p>
</main>
</header>

<main>

<section class="card">
<h2>Search jobs</h2>

<div class="grid">
<input id="q" placeholder="Job title or skill">
<input id="country" placeholder="Country">

<select id="mode">
<option value="">Any work mode</option>
<option value="remote">Remote</option>
<option value="hybrid">Hybrid</option>
<option value="onsite">On-site</option>
</select>
</div>

<button onclick="searchJobs()">Find jobs</button>
</section>

<div id="results"></div>

</main>

<script>

async function searchJobs(){

    const p = new URLSearchParams();

    if(q.value) p.set("q", q.value);
    if(country.value) p.set("country", country.value);
    if(mode.value) p.set("work_mode", mode.value);

    const r = await fetch("/api/jobs?" + p.toString());

    if(!r.ok){
        results.innerHTML =
            "<div class='card'>Unable to load jobs.</div>";
        return;
    }

    const jobs = await r.json();

    results.innerHTML = jobs.length
        ? jobs.map(j => `

<article class="card">

<h2>${esc(j.title)}</h2>

<p>
<b>${esc(j.country || "Location not listed")}</b>
· ${esc(j.work_mode || "Work mode not listed")}
</p>

<p>
${esc((j.description || "").slice(0,300))}
</p>

${j.salary_max
    ? `<p>
        Salary:
        ${esc(j.currency || "")}
        ${j.salary_min || ""}
        –
        ${j.salary_max}
       </p>`
    : ""
}

${j.application_url
    ? `<a href="${attr(j.application_url)}"
          target="_blank"
          rel="noopener noreferrer">
          <button>Apply</button>
       </a>`
    : ""
}

</article>

`).join("")
        : "<div class='card'>No matching jobs found.</div>";
}


function esc(v){
    return String(v).replace(
        /[&<>"']/g,
        c => ({
            "&":"&amp;",
            "<":"&lt;",
            ">":"&gt;",
            '"':"&quot;",
            "'":"&#039;"
        }[c])
    );
}


function attr(v){
    return String(v).replace(
        /["<>]/g,
        c => ({
            '"':"&quot;",
            "<":"&lt;",
            ">":"&gt;"
        }[c])
    );
}

</script>

</body>
</html>"""


@app.get("/api/jobs", response_model=list[JobOut])
def search_jobs(
    q: str | None = Query(default=None),
    country: str | None = Query(default=None),
    work_mode: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):

    query = db.query(Job).filter(Job.is_active.is_(True))

    if q:
        term = f"%{q}%"

        query = query.filter(
            or_(
                Job.title.ilike(term),
                Job.description.ilike(term),
                Job.skills.ilike(term),
                Job.qualifications.ilike(term),
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

    if not db.get(Employer, payload.employer_id):
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
        "match_score": match_score(seeker, job),
    }


@app.get("/api/ingestion/status")
def ingestion_status():

    return {
        "status": "ready",
        "version": APP_VERSION,
        "message": (
            "Talvexa is ready for authorised "
            "job-source integrations."
        ),
        "supported_sources": [
            "employer career pages",
            "authorised APIs",
            "licensed job feeds",
            "direct employer submissions",
        ],
    }
