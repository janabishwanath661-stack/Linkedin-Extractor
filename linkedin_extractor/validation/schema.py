"""
validation/schema.py — Pydantic v2 models for LinkedIn profile data validation.
"""

from datetime import datetime
from typing import List, Optional

from loguru import logger
from pydantic import BaseModel, Field, ValidationError


class Experience(BaseModel):
    title: str
    company: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    duration: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None


class Education(BaseModel):
    institution: str
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_year: Optional[str] = None
    end_year: Optional[str] = None


class Certification(BaseModel):
    name: str
    issuer: Optional[str] = None
    issue_date: Optional[str] = None


class LinkedInProfile(BaseModel):
    full_name: str
    headline: Optional[str] = None
    location: Optional[str] = None
    about: Optional[str] = None
    current_company: Optional[str] = None
    connections: Optional[str] = None
    experience: List[Experience] = []
    education: List[Education] = []
    skills: List[str] = []
    certifications: List[Certification] = []
    languages: List[str] = []
    email: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    confidence_score: Optional[float] = None


def validate_profile(raw_dict: dict) -> LinkedInProfile:
    """
    Validate a raw dict against the LinkedInProfile schema.

    Args:
        raw_dict: Dict parsed from LLM JSON output.

    Returns:
        Validated LinkedInProfile instance.

    Raises:
        ValidationError: With details of every field that failed.
    """
    try:
        profile = LinkedInProfile(**raw_dict)
        logger.success("Profile validated successfully for '{}'", profile.full_name)
        return profile
    except ValidationError as exc:
        for error in exc.errors():
            logger.warning("Validation error — field '{}': {}", error["loc"], error["msg"])
        raise
