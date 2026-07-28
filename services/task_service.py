from __future__ import annotations

from sqlalchemy.orm import Session

from exceptions import AppError, ForbiddenError, NotFoundError
from models import Task, TaskStatus
from repositories import ProjectRepository, TaskRepository


ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    TaskStatus.TODO.value: {TaskStatus.IN_PROGRESS.value},
    TaskStatus.IN_PROGRESS.value: {
        TaskStatus.TODO.value,
        TaskStatus.COMPLETED.value,
    },
    TaskStatus.COMPLETED.value: {TaskStatus.TODO.value},
}


class TaskService:
    def __init__(self, db: Session) -> None:
        self.projects = ProjectRepository(db)
        self.tasks = TaskRepository(db)

    def _assert_project_owner(self, project_id: int, owner_id: int) -> None:
        project = self.projects.get_with_tasks(project_id)
        if not project:
            raise NotFoundError("프로젝트를 찾을 수 없습니다.")
        if project.owner_id != owner_id:
            raise ForbiddenError()

    def list_tasks(
        self,
        *,
        project_id: int,
        owner_id: int,
        status: str = "",
        query: str = "",
    ) -> list[Task]:
        self._assert_project_owner(project_id, owner_id)
        if status and status not in {item.value for item in TaskStatus}:
            raise AppError("올바르지 않은 상태 필터입니다.")
        return self.tasks.list_for_project(
            project_id, status=status, query=query.strip()
        )

    def create_task(
        self,
        *,
        project_id: int,
        owner_id: int,
        title: str,
        description: str,
    ) -> Task:
        self._assert_project_owner(project_id, owner_id)
        title = title.strip()
        description = description.strip()
        if not 2 <= len(title) <= 120:
            raise AppError("할 일 제목은 2~120자로 입력해 주세요.")
        if len(description) > 1000:
            raise AppError("할 일 설명은 1,000자 이하여야 합니다.")
        return self.tasks.create(
            project_id=project_id,
            title=title,
            description=description,
            status=TaskStatus.TODO.value,
        )

    def change_status(
        self, *, task_id: int, owner_id: int, new_status: str
    ) -> tuple[Task, str]:
        task = self.tasks.get_by_id(task_id)
        if not task:
            raise NotFoundError("할 일을 찾을 수 없습니다.")
        self._assert_project_owner(task.project_id, owner_id)
        if new_status not in {item.value for item in TaskStatus}:
            raise AppError("올바르지 않은 상태입니다.")
        if new_status == task.status:
            raise AppError("이미 선택한 상태입니다.")
        if new_status not in ALLOWED_TRANSITIONS[task.status]:
            raise AppError(
                f"{task.status_label} 상태에서 요청한 상태로 변경할 수 없습니다."
            )
        previous_status = task.status_label
        task.status = new_status
        return self.tasks.save(task), previous_status

    def delete_task(self, *, task_id: int, owner_id: int) -> int:
        task = self.tasks.get_by_id(task_id)
        if not task:
            raise NotFoundError("할 일을 찾을 수 없습니다.")
        self._assert_project_owner(task.project_id, owner_id)
        project_id = task.project_id
        self.tasks.delete(task)
        return project_id

