import re

def tokens(value: str) -> set[str]:
    return {x for x in re.findall(r"[a-zA-Z0-9+#.-]+", (value or "").lower()) if len(x) > 1}

def match_score(profile, job) -> int:
    score = 0
    possible = 0

    profile_skills = tokens(profile.skills)
    job_skills = tokens(job.skills)

    if job_skills:
        possible += 40
        score += round(40 * len(profile_skills & job_skills) / max(1, len(job_skills)))

    possible += 20
    if profile.preferred_work_modes:
        if job.work_mode.lower() in tokens(profile.preferred_work_modes):
            score += 20

    possible += 20
    if profile.preferred_countries:
        if job.country and job.country.lower() in tokens(profile.preferred_countries):
            score += 20

    possible += 20
    if profile.minimum_salary is None:
        score += 20
    elif job.salary_max is not None and job.salary_max >= profile.minimum_salary:
        score += 20

    return min(100, round(score / max(1, possible) * 100))
