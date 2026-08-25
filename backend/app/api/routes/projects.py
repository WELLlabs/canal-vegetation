from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.job_service import create_project, get_project, list_projects

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str = "Untitled project"


class ProjectOut(BaseModel):
    project_id: str
    name: str


@router.post("", response_model=ProjectOut)
def post_project(body: ProjectCreate | None = None):
    project = create_project((body.name if body else None) or "Untitled project")
    return ProjectOut(project_id=project.id, name=project.name)


@router.get("", response_model=list[ProjectOut])
def get_projects():
    return [ProjectOut(project_id=p.id, name=p.name) for p in list_projects()]


@router.get("/{project_id}", response_model=ProjectOut)
def get_one_project(project_id: str):
    project = get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Project not found"})
    return ProjectOut(project_id=project.id, name=project.name)
