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
    match_score: Optional[float] = None


class UnifiedResident(BaseModel):
    """
    A unified view of a resident with matched benefits.
    Combines REST resident data with any matched XML benefit records.
    """
    id: str
    first_name: str
    last_name: str
    date_of_birth: Optional[str] = None
    address_line: Optional[str] = None
    city: Optional[str] = None
    phone: Optional[str] = None
    program_status: Optional[str] = None
    last_contact: Optional[str] = None
    matched_xml_data: list[BenefitRecord] = []


class ResidentsResponse(BaseModel):
    """
    The API response envelope for listing all residents.
    Contains neutral buckets for matched data, REST-only data, and XML-only data.
    """
    status: str  # "success", "partial_success", or "error"
    
    # Metadata Counters
    total_rest_records: int
    total_xml_records: int
    total_matched: int
    total_rest_only: int
    total_xml_only: int
    
    warnings: list[str] = []
    
    # The 3 Data Buckets
    matched_data: list[UnifiedResident] = []
    rest_only_data: list[Resident] = []
    xml_only_data: list[BenefitRecord] = []


class SingleResidentResponse(BaseModel):
    """
    The API response envelope for a single resident lookup.
    """
    status: str
    warnings: list[str] = []
    resident: Optional[UnifiedResident] = None
