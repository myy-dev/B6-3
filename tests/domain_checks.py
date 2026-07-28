"""Database and business-rule checks using only the standard unittest module."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path


TEMP_DIR = tempfile.TemporaryDirectory()
DB_PATH = Path(TEMP_DIR.name) / "domain-check.db"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["APP_SECRET_KEY"] = "domain-check-secret"

from database import SessionLocal, create_tables  # noqa: E402
from exceptions import AppError  # noqa: E402
from models import Project, Task, User  # noqa: E402
from services import AuthService, ProjectService, TaskService  # noqa: E402


class DomainChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        create_tables()

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
