"""Repository snapshot, ownership and pre-RETURNING SQLite regressions."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker


TEMP_DIR = tempfile.TemporaryDirectory()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["DATABASE_URL"] = f"sqlite:///{Path(TEMP_DIR.name) / 'bootstrap.db'}"

from core.database import Base, enable_sqlite_foreign_keys  # noqa: E402
from models import Project, Task  # noqa: E402
from services import AuthService, ProjectService, TaskService  # noqa: E402


class RepositoryChecks(unittest.TestCase):
    def setUp(self) -> None:
        path = Path(TEMP_DIR.name) / f"{self._testMethodName}.db"
        self.engine = create_engine(f"sqlite:///{path}")
        self.addCleanup(self.engine.dispose)
        event.listen(self.engine, "connect", enable_sqlite_foreign_keys)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(
            bind=self.engine, autoflush=False, expire_on_commit=False
        )
        with self.sessions() as db:
            users = [
                AuthService(db).register(
                    username=name, display_name=name, password="secure-pass-123"
                )
                for name in ("owner_a", "owner_b")
            ]
            self.owner_id, self.outsider_id = [user.id for user in users]
            project = ProjectService(db).create_project(
                owner_id=self.owner_id, name="원래 프로젝트", description="원래 설명"
            )
            task = TaskService(db).create_task(
                project_id=project.id, owner_id=self.owner_id,
                title="원래 작업", description="원래 작업 설명",
            )
            self.project_id, self.task_id = project.id, task.id

    def test_created_project_keeps_own_snapshot_after_commit(self) -> None:
        replaced = []

        def replace_after_commit(db):
            created = next(item for item in db.identity_map.values() if isinstance(item, Project))
            with self.sessions() as other:
                ProjectService(other).delete_project(
                    project_id=created.id, owner_id=self.owner_id
                )
                replacement = ProjectService(other).create_project(
                    owner_id=self.outsider_id, name="비공개 프로젝트", description="비공개 설명"
                )
                self.assertEqual(replacement.id, created.id)
                replaced.append(replacement.id)

        with self.sessions() as db:
            event.listen(db, "after_commit", replace_after_commit, once=True)
            created = ProjectService(db).create_project(
                owner_id=self.owner_id, name="요청한 프로젝트", description="요청한 설명"
            )
            self.assertTrue(replaced)
            self.assertEqual(created.owner_id, self.owner_id)
            self.assertEqual(created.name, "요청한 프로젝트")
            self.assertEqual(created.description, "요청한 설명")
            self.assertIsNotNone(created.created_at)

    def test_changed_task_keeps_own_snapshot_after_commit(self) -> None:
        replaced = []

        def replace_after_commit(_db):
            with self.sessions() as other:
                TaskService(other).delete_task(task_id=self.task_id, owner_id=self.owner_id)
                project = ProjectService(other).create_project(
                    owner_id=self.outsider_id, name="비공개 프로젝트", description=""
                )
                replacement = TaskService(other).create_task(
                    project_id=project.id, owner_id=self.outsider_id,
                    title="비공개 작업", description="비공개 설명",
                )
                self.assertEqual(replacement.id, self.task_id)
                replaced.append(replacement.id)

        with self.sessions() as db:
            event.listen(db, "after_commit", replace_after_commit, once=True)
            task, previous = TaskService(db).change_status(
                task_id=self.task_id, owner_id=self.owner_id, new_status="in_progress"
            )
            self.assertTrue(replaced)
            self.assertEqual(previous, "대기")
            self.assertEqual(task.title, "원래 작업")
            self.assertEqual(task.description, "원래 작업 설명")
            self.assertEqual(task.project_id, self.project_id)
            self.assertEqual(task.status, "in_progress")
            self.assertIsNotNone(task.updated_at)

    def test_project_task_loader_rechecks_current_owner(self) -> None:
        replaced = []

        def replace_before_child_query(state):
            if not state.is_relationship_load or replaced:
                return
            with self.sessions() as other:
                ProjectService(other).delete_project(
                    project_id=self.project_id, owner_id=self.owner_id
                )
                replacement = ProjectService(other).create_project(
                    owner_id=self.outsider_id, name="비공개 프로젝트", description=""
                )
                self.assertEqual(replacement.id, self.project_id)
                for index in range(3):
                    TaskService(other).create_task(
                        project_id=replacement.id, owner_id=self.outsider_id,
                        title=f"비공개 작업 {index}", description="비공개 설명",
                    )
                replaced.append(replacement.id)

        with self.sessions() as db:
            event.listen(db, "do_orm_execute", replace_before_child_query)
            projects = ProjectService(db).list_projects(self.owner_id)
            self.assertTrue(replaced)
            self.assertEqual(len(projects), 1)
            self.assertEqual(projects[0].owner_id, self.owner_id)
            self.assertEqual(projects[0].tasks, [])

    def test_crud_without_sqlite_returning_support(self) -> None:
        statements = []

        def reject_returning(_connection, _cursor, statement, _parameters, _context, _many):
            statements.append(statement)
            self.assertNotIn("RETURNING", statement.upper())

        with ExitStack() as stack:
            for flag in ("insert_returning", "update_returning", "delete_returning"):
                stack.enter_context(patch.object(self.engine.dialect, flag, False))
            event.listen(self.engine, "before_cursor_execute", reject_returning)
            self.addCleanup(event.remove, self.engine, "before_cursor_execute", reject_returning)
            with self.sessions() as db:
                project = ProjectService(db).create_project(
                    owner_id=self.owner_id, name="구버전 호환 검사", description=""
                )
                tasks = [
                    TaskService(db).create_task(
                        project_id=project.id, owner_id=self.owner_id,
                        title=f"호환 작업 {index}", description="",
                    )
                    for index in range(2)
                ]
                project_id, task_ids = project.id, [task.id for task in tasks]
                task, previous = TaskService(db).change_status(
                    task_id=task_ids[0], owner_id=self.owner_id, new_status="in_progress"
                )
                self.assertEqual(previous, "대기")
                self.assertEqual(task.status, "in_progress")
                self.assertIsNotNone(task.created_at)
                self.assertIsNotNone(task.updated_at)
                loaded = TaskService(db).list_tasks(
                    project_id=project_id, owner_id=self.owner_id, status="in_progress"
                )
                self.assertEqual([item.id for item in loaded], [task_ids[0]])
                TaskService(db).delete_task(task_id=task_ids[0], owner_id=self.owner_id)
                ProjectService(db).delete_project(project_id=project_id, owner_id=self.owner_id)
                self.assertIsNone(db.get(Project, project_id))
                self.assertIsNone(db.get(Task, task_ids[1]))
        self.assertTrue(statements)


if __name__ == "__main__":
    unittest.main(verbosity=2)
