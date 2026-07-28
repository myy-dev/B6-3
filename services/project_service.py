from __future__ import annotations

from sqlalchemy.orm import Session

from exceptions import AppError, ForbiddenError, NotFoundError
from models import Project
from repositories import ProjectRepository


class ProjectService:
    def __init__(self, db: Session) -> None:
        self.projects = ProjectRepository(db)

    def list_projects(self, owner_id: int, *, query: str = "") -> list[Project]:
        return self.projects.list_for_owner(owner_id, query=query.strip())

    def get_owned_project(self, project_id: int, owner_id: int) -> Project:
        project = self.projects.get_with_tasks(project_id)
        if not project:
            raise NotFoundError("프로젝트를 찾을 수 없습니다.")
        if project.owner_id != owner_id:
            raise ForbiddenError()
        return project

    def create_project(
        self, *, owner_id: int, name: str, description: str
    ) -> Project:
        name = name.strip()
        description = description.strip()
        if not 2 <= len(name) <= 100:
            raise AppError("프로젝트 이름은 2~100자로 입력해 주세요.")
        if len(description) > 1000:
            raise AppError("프로젝트 설명은 1,000자 이하여야 합니다.")
        return self.projects.create(
            owner_id=owner_id, name=name, description=description
        )

    def delete_project(self, *, project_id: int, owner_id: int) -> None:
        project = self.get_owned_project(project_id, owner_id)
        self.projects.delete(project)

    def dashboard_counts(self, owner_id: int) -> tuple[int, int, int]:
        return self.projects.dashboard_counts(owner_id)

