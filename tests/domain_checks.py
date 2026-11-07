"""Database and business-rule checks using only the standard unittest module."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

from fastapi import Request
from passlib.utils import MAX_PASSWORD_SIZE
from sqlalchemy import inspect


TEMP_DIR = tempfile.TemporaryDirectory()
DB_PATH = Path(TEMP_DIR.name) / "domain-check.db"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["APP_SECRET_KEY"] = "domain-check-secret"

from auth.security import start_session, validate_csrf  # noqa: E402
from core.database import SessionLocal, create_tables  # noqa: E402
from core.exceptions import AppError, ForbiddenError, NotFoundError  # noqa: E402
from models import Project, Task, User  # noqa: E402
from repositories import UserRepository  # noqa: E402
from routers.auth import github_callback  # noqa: E402
from services import AuthService, ProjectService, TaskService  # noqa: E402


class DomainChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        create_tables()

    def test_reused_ids_cannot_access_another_owners_data(self) -> None:
        for operation in ("delete_task", "delete_project", "create_task", "list_tasks"):
            with self.subTest(operation=operation), SessionLocal() as db:
                users = [
                    AuthService(db).register(
                        username=f"paths_{operation}_{suffix}",
                        display_name="경로별 권한 검사", password="secure-pass-123",
                    )
                    for suffix in ("owner", "outsider")
                ]
                owner_id, outsider_id = [user.id for user in users]
                project = ProjectService(db).create_project(
                    owner_id=owner_id, name="원래 프로젝트", description=""
                )
                task = TaskService(db).create_task(
                    project_id=project.id, owner_id=owner_id,
                    title="원래 작업", description="",
                )
                project_id, task_id = project.id, task.id
                service = (
                    ProjectService(db) if operation == "delete_project" else TaskService(db)
                )
                repository = (
                    service.projects if operation == "delete_project" else service.tasks
                )
                method = {
                    "delete_task": "delete", "delete_project": "delete",
                    "create_task": "create", "list_tasks": "list_for_project",
                }[operation]
                original = getattr(repository, method)
                replacement_ids = []

                def replace_before_operation(*args, **kwargs):
                    with SessionLocal() as other:
                        if operation == "delete_task":
                            TaskService(other).delete_task(
                                task_id=task_id, owner_id=owner_id
                            )
                        else:
                            ProjectService(other).delete_project(
                                project_id=project_id, owner_id=owner_id
                            )
                        replacement_project = ProjectService(other).create_project(
                            owner_id=outsider_id, name="다른 사용자 프로젝트", description=""
                        )
                        replacement = TaskService(other).create_task(
                            project_id=replacement_project.id, owner_id=outsider_id,
                            title="비공개 작업", description="비공개 설명",
                        )
                        self.assertEqual(replacement.id, task_id)
                        if operation != "delete_task":
                            self.assertEqual(replacement_project.id, project_id)
                        replacement_ids.append(replacement_project.id)
                    return original(*args, **kwargs)

                with patch.object(repository, method, replace_before_operation):
                    if operation == "list_tasks":
                        self.assertEqual(
                            service.list_tasks(project_id=project_id, owner_id=owner_id), []
                        )
                    else:
                        with self.assertRaises(AppError) as error:
                            if operation == "delete_task":
                                service.delete_task(task_id=task_id, owner_id=owner_id)
                            elif operation == "delete_project":
                                service.delete_project(project_id=project_id, owner_id=owner_id)
                            else:
                                service.create_task(
                                    project_id=project_id, owner_id=owner_id,
                                    title="권한 없는 작업", description="",
                                )
                        self.assertEqual(error.exception.status_code, 409)
                with SessionLocal() as other:
                    replacement_project = other.get(Project, replacement_ids[0])
                    self.assertIsNotNone(replacement_project)
                    self.assertEqual(replacement_project.owner_id, outsider_id)
                    self.assertEqual(
                        [(item.id, item.title, item.description) for item in replacement_project.tasks],
                        [(task_id, "비공개 작업", "비공개 설명")],
                    )

    def test_project_delete_cascades_with_loaded_tasks(self) -> None:
        with SessionLocal() as db:
            user = AuthService(db).register(
                username="loaded_delete", display_name="연쇄 삭제 검사",
                password="secure-pass-123",
            )
            project = ProjectService(db).create_project(
                owner_id=user.id, name="연쇄 삭제 검사", description=""
            )
            tasks = [
                TaskService(db).create_task(
                    project_id=project.id, owner_id=user.id, title=f"작업 {index}", description=""
                )
                for index in range(2)
            ]
            project_id, task_ids = project.id, [task.id for task in tasks]
            self.assertEqual(len(project.tasks), 2)
            ProjectService(db).delete_project(project_id=project_id, owner_id=user.id)
            self.assertIsNone(db.get(Project, project_id))
            for task_id in task_ids:
                self.assertIsNone(db.get(Task, task_id))

    def test_reused_task_id_cannot_change_another_owners_task(self) -> None:
        for reuse_project_id in (False, True):
            with self.subTest(reuse_project_id=reuse_project_id), SessionLocal() as db:
                users = [
                    AuthService(db).register(
                        username=f"reuse_{reuse_project_id}_{suffix}",
                        display_name="ID 재사용 검사", password="secure-pass-123",
                    )
                    for suffix in ("owner", "outsider")
                ]
                owner_id, outsider_id = [user.id for user in users]
                project = ProjectService(db).create_project(
                    owner_id=owner_id, name="원래 프로젝트", description=""
                )
                service = TaskService(db)
                task = service.create_task(
                    project_id=project.id, owner_id=owner_id,
                    title="원래 작업", description="",
                )
                task_id, project_id = task.id, project.id
                original_save = service.tasks.change_status

                def replace_before_save(task, **changes):
                    # Interleave deletion/creation after authorization, before the write.
                    with SessionLocal() as other:
                        if reuse_project_id:
                            ProjectService(other).delete_project(
                                project_id=project_id, owner_id=owner_id
                            )
                        else:
                            TaskService(other).delete_task(
                                task_id=task_id, owner_id=owner_id
                            )
                        replacement_project = ProjectService(other).create_project(
                            owner_id=outsider_id, name="다른 사용자 프로젝트", description=""
                        )
                        replacement = TaskService(other).create_task(
                            project_id=replacement_project.id, owner_id=outsider_id,
                            title="다른 사용자 작업", description="",
                        )
                        self.assertEqual(replacement.id, task_id)
                        if reuse_project_id:
                            self.assertEqual(replacement_project.id, project_id)
                    return original_save(task, **changes)

                with patch.object(service.tasks, "change_status", replace_before_save):
                    with self.assertRaises(AppError) as error:
                        service.change_status(
                            task_id=task_id, owner_id=owner_id, new_status="in_progress"
                        )
                self.assertEqual(error.exception.status_code, 409)
                with SessionLocal() as other:
                    replacement = other.get(Task, task_id)
                    self.assertEqual(replacement.status, "todo")
                    self.assertEqual(replacement.project.owner_id, outsider_id)

    def test_stale_status_change_is_rejected(self) -> None:
        with SessionLocal() as db:
            user = AuthService(db).register(
                username="race_owner", display_name="동시 변경", password="secure-pass-123"
            )
            project = ProjectService(db).create_project(
                owner_id=user.id, name="동시 변경", description=""
            )
            task = TaskService(db).create_task(
                project_id=project.id, owner_id=user.id, title="동시 변경", description=""
            )
            TaskService(db).change_status(
                task_id=task.id, owner_id=user.id, new_status="in_progress"
            )
            user_id, task_id = user.id, task.id

        with SessionLocal() as first, SessionLocal() as second:
            first_task = first.get(Task, task_id)
            stale_task = second.get(Task, task_id)
            self.assertEqual(first_task.status, stale_task.status)
            TaskService(first).change_status(
                task_id=task_id, owner_id=user_id, new_status="todo"
            )
            with self.assertRaises(AppError) as error:
                TaskService(second).change_status(
                    task_id=task_id, owner_id=user_id, new_status="completed"
                )
            self.assertEqual(error.exception.status_code, 409)
            self.assertEqual(second.get(Task, task_id).status, "todo")
            TaskService(second).change_status(
                task_id=task_id, owner_id=user_id, new_status="in_progress"
            )
        with SessionLocal() as db:
            self.assertEqual(db.get(Task, task_id).status, "in_progress")

    def test_concurrent_signup_returns_duplicate_error(self) -> None:
        barrier = Barrier(2)
        original_lookup = UserRepository.get_by_username

        def lookup(repository, username):
            user = original_lookup(repository, username)
            if username == "race_signup" and user is None:
                barrier.wait(timeout=5)
            return user

        def register():
            with SessionLocal() as db:
                service = AuthService(db)
                try:
                    service.register(
                        username="race_signup", display_name="동시 가입",
                        password="secure-pass-123",
                    )
                    return "created"
                except AppError as error:
                    self.assertEqual(error.status_code, 400)
                    self.assertIsNotNone(service.users.get_by_username("race_signup"))
                    return error.message

        with patch.object(UserRepository, "get_by_username", lookup):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: register(), range(2)))
        self.assertCountEqual(results, ["created", "이미 사용 중인 아이디입니다."])

    def test_concurrent_oauth_creation_reuses_same_user(self) -> None:
        barrier = Barrier(2)
        original_lookup = UserRepository.get_by_oauth_identity

        def lookup(repository, provider, subject):
            user = original_lookup(repository, provider, subject)
            if subject == "race-oauth" and user is None:
                barrier.wait(timeout=5)
            return user

        def authenticate():
            with SessionLocal() as db:
                user = AuthService(db).get_or_create_oauth_user(
                    provider="github", subject="race-oauth",
                    suggested_username="race_oauth", display_name="동시 소셜 로그인",
                )
                return user.id

        with patch.object(UserRepository, "get_by_oauth_identity", lookup):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: authenticate(), range(2)))
        self.assertEqual(results[0], results[1])

    def test_unicode_tokens_return_validation_errors(self) -> None:
        request = Request({"type": "http", "session": {"csrf_token": "ascii-token"}})
        with self.assertRaises(AppError) as error:
            validate_csrf(request, "한글")
        self.assertEqual(error.exception.status_code, 403)
        request.session["oauth_state"] = "ascii-state"
        with self.assertRaises(AppError) as error:
            github_callback(request, None, code="unused", state="한글")
        self.assertEqual(error.exception.status_code, 401)

    def test_password_size_boundaries(self) -> None:
        with SessionLocal() as db:
            service = AuthService(db)
            password = "x" * MAX_PASSWORD_SIZE
            user = service.register(
                username="password_boundary", display_name="길이 검사", password=password
            )
            self.assertEqual(
                service.authenticate(username=user.username, password=password).id,
                user.id,
            )
            for oversized in (password + "x", "한" * (MAX_PASSWORD_SIZE + 1)):
                with self.subTest(password_type=oversized[0]):
                    with self.assertRaises(AppError) as error:
                        service.register(
                            username="too_long", display_name="길이 검사", password=oversized
                        )
                    self.assertEqual(error.exception.status_code, 400)
                    with self.assertRaises(AppError) as error:
                        service.authenticate(username=user.username, password=oversized)
                    self.assertEqual(error.exception.status_code, 401)

    def test_start_session_discards_previous_session_data(self) -> None:
        request = Request(
            {
                "type": "http",
                "session": {
                    "user_id": 99,
                    "csrf_token": "old-token",
                    "oauth_state": "old-state",
                },
            }
        )
        start_session(request, 1)
        self.assertEqual(request.session, {"user_id": 1})

    def test_task_access_and_filtered_detail(self) -> None:
        with SessionLocal() as db:
            owner, outsider = (
                AuthService(db).register(
                    username=username, display_name=username, password="secure-pass-123"
                )
                for username in ("detail_owner", "detail_outsider")
            )
            project = ProjectService(db).create_project(
                owner_id=owner.id, name="상세 조회", description=""
            )
            service = TaskService(db)
            task = service.create_task(
                project_id=project.id, owner_id=owner.id, title="검색 대상", description=""
            )
            for operation in (
                lambda: ProjectService(db).get_owned_project(project.id, outsider.id),
                lambda: service.get_project_detail(
                    project_id=project.id, owner_id=outsider.id
                ),
                lambda: service.list_tasks(
                    project_id=project.id, owner_id=outsider.id
                ),
                lambda: service.create_task(
                    project_id=project.id, owner_id=outsider.id,
                    title="침입", description="",
                ),
                lambda: service.change_status(
                    task_id=task.id, owner_id=outsider.id, new_status="in_progress"
                ),
                lambda: service.delete_task(task_id=task.id, owner_id=outsider.id),
            ):
                with self.assertRaises(ForbiddenError):
                    operation()

            loaded, tasks = service.get_project_detail(
                project_id=project.id, owner_id=owner.id, status="todo", query="  검색  "
            )
            self.assertEqual(loaded.id, project.id)
            self.assertEqual([item.id for item in tasks], [task.id])
            self.assertIn("tasks", inspect(loaded).unloaded)
            self.assertEqual(
                service.list_tasks(
                    project_id=project.id, owner_id=owner.id, status="completed"
                ),
                [],
            )
            with self.assertRaises(AppError):
                service.list_tasks(
                    project_id=project.id, owner_id=owner.id, status="invalid"
                )

            self.assertEqual(
                service.delete_task(task_id=task.id, owner_id=owner.id), project.id
            )
            for operation in (
                lambda: service.delete_task(task_id=task.id, owner_id=owner.id),
                lambda: service.change_status(
                    task_id=task.id, owner_id=owner.id, new_status="in_progress"
                ),
            ):
                with self.assertRaises(NotFoundError):
                    operation()
            child = service.create_task(
                project_id=project.id, owner_id=owner.id, title="연쇄 삭제", description=""
            )
            project_id, owner_id, child_id = project.id, owner.id, child.id
            db.expire_all()
            ProjectService(db).delete_project(project_id=project_id, owner_id=owner_id)
            self.assertIsNone(db.get(Task, child_id))
            with self.assertRaises(NotFoundError):
                service.get_project_detail(project_id=project_id, owner_id=owner_id)

    def test_relationships_hashing_transitions_and_cascade(self) -> None:
        with SessionLocal() as db:
            user = AuthService(db).register(
                username="domain_user",
                display_name="도메인 사용자",
                password="secure-pass-123",
            )
            self.assertNotEqual(user.password_hash, "secure-pass-123")
            self.assertTrue(user.password_hash.startswith("$pbkdf2-sha256$"))

            project = ProjectService(db).create_project(
                owner_id=user.id,
                name="관계 검증",
                description="두 개의 1:N 관계",
            )
            task = TaskService(db).create_task(
                project_id=project.id,
                owner_id=user.id,
                title="상태 검증",
                description="비즈니스 규칙 확인",
            )

            loaded_user = db.get(User, user.id)
            loaded_project = db.get(Project, project.id)
            db.expire(loaded_user, ["projects"])
            db.expire(loaded_project, ["tasks"])
            self.assertEqual([item.id for item in loaded_user.projects], [project.id])
            self.assertEqual([item.id for item in loaded_project.tasks], [task.id])

            with self.assertRaises(AppError):
                TaskService(db).change_status(
                    task_id=task.id,
                    owner_id=user.id,
                    new_status="completed",
                )
            task, before = TaskService(db).change_status(
                task_id=task.id,
                owner_id=user.id,
                new_status="in_progress",
            )
            self.assertEqual(before, "대기")
            self.assertEqual(task.status_label, "진행 중")
            task, before = TaskService(db).change_status(
                task_id=task.id,
                owner_id=user.id,
                new_status="completed",
            )
            self.assertEqual(before, "진행 중")
            self.assertEqual(task.status_label, "완료")

            user_id, project_id, task_id = user.id, project.id, task.id
            db.delete(user)
            db.commit()
            self.assertIsNone(db.get(User, user_id))
            self.assertIsNone(db.get(Project, project_id))
            self.assertIsNone(db.get(Task, task_id))


if __name__ == "__main__":
    unittest.main(verbosity=2)
