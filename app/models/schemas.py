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


class ResidentsResponse(BaseModel):
    """
    The API response envelope.
    Contains the data, a status indicator, and any warnings.
    """
    status: str  # "success" or "partial_success"
    total_residents: int
    warnings: list[str] = []
    residents: list[Resident] = []
