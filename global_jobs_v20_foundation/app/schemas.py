from typing import Optional
from pydantic import BaseModel, ConfigDict

class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    employer_id: int
    title: str
    description: str
    country: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    work_mode: str
    employment_type: str
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    currency: Optional[str] = None
    skills: str
    qualifications: str
    work_authorisation: str
    application_url: Optional[str] = None
    source: Optional[str] = None
    is_active: bool

class JobCreate(BaseModel):
    employer_id: int
    title: str
    description: str
    country: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    work_mode: str = "onsite"
    employment_type: str = "full-time"
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    currency: Optional[str] = None
    skills: str = ""
    qualifications: str = ""
    work_authorisation: str = ""
    application_url: Optional[str] = None
    source: Optional[str] = None
    source_url: Optional[str] = None
