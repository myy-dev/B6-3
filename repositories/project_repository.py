from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from models import Project, Task


class ProjectRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_owner(self, owner_id: int, *, query: str = "") -> list[Project]:
        statement = (
            select(Project)
            .where(Project.owner_id == owner_id)
            .options(selectinload(Project.tasks))
            .order_by(Project.created_at.desc())
        )
        if query:
            pattern = f"%{query}%"
            statement = statement.where(
                or_(Project.name.ilike(pattern), Project.description.ilike(pattern))
            )
        return list(self.db.scalars(statement).all())

    def get_with_tasks(self, project_id: int) -> Project | None:
        return self.db.scalar(
            select(Project)
            .where(Project.id == project_id)
            .options(selectinload(Project.tasks), selectinload(Project.owner))
        )

    def create(self, *, owner_id: int, name: str, description: str) -> Project:
        project = Project(owner_id=owner_id, name=name, description=description)
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def delete(self, project: Project) -> None:
        self.db.delete(project)
        self.db.commit()

    def dashboard_counts(self, owner_id: int) -> tuple[int, int, int]:
        project_count = self.db.scalar(
            select(func.count(Project.id)).where(Project.owner_id == owner_id)
        ) or 0
        task_count = self.db.scalar(
            select(func.count(Task.id))
            .join(Project)
            .where(Project.owner_id == owner_id)
        ) or 0
        completed_count = self.db.scalar(
            select(func.count(Task.id))
            .join(Project)
            .where(Project.owner_id == owner_id, Task.status == "completed")
        ) or 0
        return project_count, task_count, completed_count

