from datetime import datetime
from pydantic import BaseModel, ConfigDict
from api.models.job import JobState


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    arq_job_id: str | None
    event_type: str
    delivery_id: str | None
    repository_full_name: str | None
    state: JobState
    attempts: int
    max_attempts: int
    error_message: str | None
    scheduled_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
