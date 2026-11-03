from __future__ import annotations

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session, selectinload

from models import Project, Task


class ProjectRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_owner(self, owner_id: int, *, query: str = "") -> list[Project]:
        statement = (
            select(Project)
            .where(Project.owner_id == owner_id)
            .options(
                selectinload(
                    Project.tasks.and_(Task.project.has(Project.owner_id == owner_id))
                )
            )
            .order_by(Project.created_at.desc())
        )
        if query:
            pattern = f"%{query}%"
            statement = statement.where(
                or_(Project.name.ilike(pattern), Project.description.ilike(pattern))
            )
        return list(self.db.scalars(statement).all())

    def get_by_id(self, project_id: int) -> Project | None:
        return self.db.get(Project, project_id)

    def create(self, *, owner_id: int, name: str, description: str) -> Project:
        project = Project(owner_id=owner_id, name=name, description=description)
        self.db.add(project)
        self.db.commit()
        return project

    def delete(self, project: Project, *, owner_id: int) -> bool:
        # DB cascade removes children only when the authorized parent is deleted.
        result = self.db.execute(
            delete(Project)
            .where(Project.id == project.id, Project.owner_id == owner_id)
            .execution_options(synchronize_session="fetch")
        )
        if result.rowcount != 1:
            self.db.rollback()
            return False
        self.db.commit()
        self.db.expire_all()
        return True

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

