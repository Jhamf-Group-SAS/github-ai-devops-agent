from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    github_id: int
    login: str
    name: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
