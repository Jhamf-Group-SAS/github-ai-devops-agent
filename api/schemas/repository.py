from datetime import datetime
from pydantic import BaseModel, ConfigDict


class RepositoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    github_id: int
    full_name: str
    name: str
    default_branch: str
    private: bool
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class RepositoryCreate(BaseModel):
    github_id: int
    organization_id: int
    full_name: str
    name: str
    default_branch: str = "main"
    private: bool = True
    description: str | None = None
