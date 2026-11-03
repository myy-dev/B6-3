from __future__ import annotations

from sqlalchemy import delete, insert, literal, or_, select, update
from sqlalchemy.orm import Session

from models import Project, Task


class TaskRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, task_id: int) -> Task | None:
        return self.db.get(Task, task_id)

    def list_for_project(
        self,
        project_id: int,
        *,
        owner_id: int,
        status: str = "",
        query: str = "",
    ) -> list[Task]:
        statement = select(Task).where(
            Task.project_id == project_id,
            Task.project.has(Project.owner_id == owner_id),
        )
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
        self, *, project_id: int, owner_id: int, title: str, description: str, status: str
    ) -> Task | None:
        # Authorize the parent in the INSERT itself; it may have been replaced.
        statement = (
            insert(Task)
            .from_select(
                ["project_id", "title", "description", "status"],
                select(Project.id, literal(title), literal(description), literal(status))
                .where(Project.id == project_id, Project.owner_id == owner_id),
            )
        )
        result = self.db.execute(statement)
        if result.rowcount != 1:
            self.db.rollback()
            return None
        # Read our inserted row while the write transaction still holds the lock.
        # cursor.lastrowid also works on SQLite releases without RETURNING.
        task = self.db.scalar(
            select(Task)
            .where(
                Task.id == result.lastrowid,
                Task.project_id == project_id,
                Task.project.has(Project.owner_id == owner_id),
            )
            .execution_options(populate_existing=True)
        )
        if task is None:
            self.db.rollback()
            return None
        self.db.commit()
        return task

    def change_status(self, task: Task, *, owner_id: int, new_status: str) -> bool:
        # Recheck ownership in the write even if a deleted ID has been reused.
        result = self.db.execute(
            update(Task)
            .where(
                Task.id == task.id,
                Task.project_id == task.project_id,
                Task.status == task.status,
                Task.project.has(Project.owner_id == owner_id),
            )
            .values(status=new_status)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            self.db.rollback()
            return False
        self.db.refresh(task)
        self.db.commit()
        return True

    def delete(self, task: Task, *, owner_id: int) -> bool:
        result = self.db.execute(
            delete(Task)
            .where(
                Task.id == task.id,
                Task.project_id == task.project_id,
                Task.project.has(Project.owner_id == owner_id),
            )
            .execution_options(synchronize_session="fetch")
        )
        if result.rowcount != 1:
            self.db.rollback()
            return False
        self.db.commit()
        return True

