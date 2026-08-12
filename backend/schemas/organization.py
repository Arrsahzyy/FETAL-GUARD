from datetime import datetime

from pydantic import BaseModel


class OrganizationSummary(BaseModel):
    id: str
    slug: str
    name: str

    model_config = {"from_attributes": True}


class OrganizationMembershipSummary(BaseModel):
    id: str
    role: str
    permissions: list[str]
    created_at: datetime
    organization: OrganizationSummary


class OrganizationMembershipListResponse(BaseModel):
    items: list[OrganizationMembershipSummary]
