import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models.repository import Repository
from api.schemas.repository import RepositoryCreate, RepositoryOut

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[RepositoryOut])
async def list_projects(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> list[Repository]:
    result = await db.execute(
        select(Repository)
        .where(Repository.is_active.is_(True))
        .offset(skip)
        .limit(limit)
        .order_by(Repository.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{project_id}", response_model=RepositoryOut)
async def get_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> Repository:
    result = await db.execute(select(Repository).where(Repository.id == project_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return repo


@router.post("", response_model=RepositoryOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: RepositoryCreate,
    db: AsyncSession = Depends(get_db),
) -> Repository:
    repo = Repository(**payload.model_dump())
    db.add(repo)
    await db.commit()
    await db.refresh(repo)
    logger.info("Repository registered", full_name=repo.full_name)
    return repo


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(Repository).where(Repository.id == project_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    repo.is_active = False
    await db.commit()
    logger.info("Repository deactivated", project_id=project_id)
