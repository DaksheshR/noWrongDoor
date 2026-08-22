"""
Pydantic models for the unified API response.
"""

from pydantic import BaseModel
from typing import Optional


class Resident(BaseModel):
    """A single resident from the REST Resident Index."""
    id: str
    first_name: str
    last_name: str
    date_of_birth: Optional[str] = None
    address_line: Optional[str] = None
    city: Optional[str] = None
    phone: Optional[str] = None
    program_status: Optional[str] = None
    last_contact: Optional[str] = None


class BenefitRecord(BaseModel):
    """A single benefit record from the XML Benefits Register."""
    ref: Optional[str] = None
    name: Optional[str] = None
    born: Optional[str] = None
    address: Optional[str] = None
    town: Optional[str] = None
    benefit_code: Optional[str] = None
    review_due: Optional[str] = None


class ResidentsResponse(BaseModel):
    """
    The API response envelope for listing all residents.
    Contains data from both sources, a status indicator, and any warnings.
    """
    status: str  # "success", "partial_success", or "error"
    total_residents: int
    total_benefits: int
    warnings: list[str] = []
    residents: list[Resident] = []
    benefits: list[BenefitRecord] = []


class SingleResidentResponse(BaseModel):
    """
    The API response envelope for a single resident lookup.
    """
    status: str
    warnings: list[str] = []
    resident: Optional[Resident] = None
    benefits: list[BenefitRecord] = []
