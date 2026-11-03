from __future__ import annotations

from sqlalchemy.orm import Session

from exceptions import AppError, NotFoundError
from models import Project, Task, TaskStatus
from repositories import TaskRepository
from services.project_service import ProjectService


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
        self.projects = ProjectService(db)
        self.tasks = TaskRepository(db)

    def _get_owned_task(self, task_id: int, owner_id: int) -> Task:
        task = self.tasks.get_by_id(task_id)
        if not task:
            raise NotFoundError("할 일을 찾을 수 없습니다.")
        self.projects.get_owned_project(task.project_id, owner_id)
        return task

    def list_tasks(
        self,
        *,
        project_id: int,
        owner_id: int,
        status: str = "",
        query: str = "",
    ) -> list[Task]:
        _, tasks = self.get_project_detail(
            project_id=project_id, owner_id=owner_id, status=status, query=query
        )
        return tasks

    def get_project_detail(
        self,
        *,
        project_id: int,
        owner_id: int,
        status: str = "",
        query: str = "",
    ) -> tuple[Project, list[Task]]:
        project = self.projects.get_owned_project(project_id, owner_id)
        if status and status not in {item.value for item in TaskStatus}:
            raise AppError("올바르지 않은 상태 필터입니다.")
        tasks = self.tasks.list_for_project(
            project_id, owner_id=owner_id, status=status, query=query.strip()
        )
        return project, tasks

    def create_task(
        self,
        *,
        project_id: int,
        owner_id: int,
        title: str,
        description: str,
    ) -> Task:
        self.projects.get_owned_project(project_id, owner_id)
        title = title.strip()
        description = description.strip()
        if not 2 <= len(title) <= 120:
            raise AppError("할 일 제목은 2~120자로 입력해 주세요.")
        if len(description) > 1000:
            raise AppError("할 일 설명은 1,000자 이하여야 합니다.")
        task = self.tasks.create(
            project_id=project_id,
            owner_id=owner_id,
            title=title,
            description=description,
            status=TaskStatus.TODO.value,
        )
        if task is None:
            raise AppError(
                "다른 요청에서 프로젝트가 변경되었습니다. 페이지를 새로고침해 주세요.",
                status_code=409,
            )
        return task

    def change_status(
        self, *, task_id: int, owner_id: int, new_status: str
    ) -> tuple[Task, str]:
        task = self._get_owned_task(task_id, owner_id)
        if new_status not in {item.value for item in TaskStatus}:
            raise AppError("올바르지 않은 상태입니다.")
        if new_status == task.status:
            raise AppError("이미 선택한 상태입니다.")
        if new_status not in ALLOWED_TRANSITIONS[task.status]:
            raise AppError(
                f"{task.status_label} 상태에서 요청한 상태로 변경할 수 없습니다."
            )
        previous_status = task.status_label
        if not self.tasks.change_status(task, owner_id=owner_id, new_status=new_status):
            raise AppError(
                "다른 요청에서 할 일이 변경되었습니다. 페이지를 새로고침해 주세요.",
                status_code=409,
            )
        return task, previous_status

    def delete_task(self, *, task_id: int, owner_id: int) -> int:
        task = self._get_owned_task(task_id, owner_id)
        project_id = task.project_id
        if not self.tasks.delete(task, owner_id=owner_id):
            raise AppError(
                "다른 요청에서 할 일이 변경되었습니다. 페이지를 새로고침해 주세요.",
                status_code=409,
            )
        return project_id

