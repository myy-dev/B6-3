from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from models import Task


class TaskRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, task_id: int) -> Task | None:
        return self.db.get(Task, task_id)

    def list_for_project(
        self,
        project_id: int,
        *,
        status: str = "",
        query: str = "",
    ) -> list[Task]:
        statement = select(Task).where(Task.project_id == project_id)
        if status:
            statement = statement.where(Task.status == status)
        if query:
            pattern = f"%{query}%"
            statement = statement.where(
                or_(Task.title.ilike(pattern), Task.description.ilike(pattern))
            )
        statement = statement.order_by(Task.created_at.desc())
        return list(self.db.scalars(statement).all())

    def create(
        self, *, project_id: int, title: str, description: str, status: str
    ) -> Task:
        task = Task(
            project_id=project_id,
            title=title,
            description=description,
            status=status,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def save(self, task: Task) -> Task:
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def delete(self, task: Task) -> None:
        self.db.delete(task)
        self.db.commit()

