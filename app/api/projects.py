"""プロジェクト管理API（設計書 17.7.3）。"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from ..repository.project_repository import ProjectRepository
from .schemas import (
    ProjectCreateRequest,
    ProjectDetail,
    ProjectDuplicateRequest,
    ProjectSummary,
    ProjectUpdateRequest,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])


@lru_cache(maxsize=1)
def get_repository() -> ProjectRepository:
    return ProjectRepository()


Repository = Annotated[ProjectRepository, Depends(get_repository)]


@router.get("", response_model=list[ProjectSummary])
def list_projects(repository: Repository) -> list[ProjectSummary]:
    return [ProjectSummary(**summary) for summary in repository.list()]


@router.post("", response_model=ProjectDetail, status_code=201)
def create_project(request: ProjectCreateRequest, repository: Repository) -> ProjectDetail:
    project = repository.create(
        name=request.name,
        notes=[note.model_dump() for note in request.notes] if request.notes is not None else None,
        measures=(
            [measure.model_dump() for measure in request.measures]
            if request.measures is not None
            else None
        ),
        settings=request.settings,
    )
    return ProjectDetail(**project)


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(project_id: str, repository: Repository) -> ProjectDetail:
    project = repository.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="プロジェクトが見つかりません")
    return ProjectDetail(**project)


@router.put("/{project_id}", response_model=ProjectDetail)
def update_project(
    project_id: str, request: ProjectUpdateRequest, repository: Repository
) -> ProjectDetail:
    patch = {
        "name": request.name,
        "notes": [note.model_dump() for note in request.notes] if request.notes is not None else None,
        "measures": (
            [measure.model_dump() for measure in request.measures]
            if request.measures is not None
            else None
        ),
        "settings": request.settings,
        "generatedTab": request.generatedTab,
    }
    project = repository.update(project_id, patch)
    if project is None:
        raise HTTPException(status_code=404, detail="プロジェクトが見つかりません")
    return ProjectDetail(**project)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, repository: Repository) -> None:
    if not repository.delete(project_id):
        raise HTTPException(status_code=404, detail="プロジェクトが見つかりません")


@router.post("/{project_id}/duplicate", response_model=ProjectDetail, status_code=201)
def duplicate_project(
    project_id: str, request: ProjectDuplicateRequest, repository: Repository
) -> ProjectDetail:
    project = repository.duplicate(project_id, request.name)
    if project is None:
        raise HTTPException(status_code=404, detail="プロジェクトが見つかりません")
    return ProjectDetail(**project)
