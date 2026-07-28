"""Standard-library integration test for a running FlowTask server.

Run with: FLOWTASK_BASE_URL=http://127.0.0.1:8765 .venv/bin/python tests/integration_smoke.py
"""

from __future__ import annotations

import http.cookiejar
import os
import re
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request


BASE_URL = os.getenv("FLOWTASK_BASE_URL", "http://127.0.0.1:8000")


class Browser:
    def __init__(self) -> None:
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookies)
        )

    def request(
        self,
        path: str,
        *,
        data: dict[str, str] | None = None,
    ) -> tuple[int, str, str]:
        encoded = urllib.parse.urlencode(data).encode() if data is not None else None
        request = urllib.request.Request(BASE_URL + path, data=encoded)
        try:
            with self.opener.open(request, timeout=10) as response:
                return response.status, response.geturl(), response.read().decode()
        except urllib.error.HTTPError as exc:
            try:
                return exc.code, exc.geturl(), exc.read().decode()
            finally:
                exc.close()

    def csrf(self, path: str) -> tuple[str, str]:
        status, _url, body = self.request(path)
        if status != 200:
            raise AssertionError(f"GET {path} returned {status}")
        match = re.search(r'name="csrf" value="([^"]+)"', body)
        if not match:
            raise AssertionError(f"CSRF token not found on {path}")
        return match.group(1), body


class FlowTaskIntegrationTest(unittest.TestCase):
    def test_complete_user_flow(self) -> None:
        anonymous = Browser()
        status, final_url, body = anonymous.request("/app/projects")
        self.assertEqual(status, 200)
        self.assertIn("/login?next=/app/projects", final_url)
        self.assertIn("로그인", body)

        status, _url, body = anonymous.request("/login", data={
            "csrf": anonymous.csrf("/login")[0],
            "username": "demo",
            "password": "wrong-password",
            "next_url": "/app/projects",
        })
        self.assertEqual(status, 401)
        self.assertIn("아이디 또는 비밀번호가 올바르지 않습니다", body)

        browser = Browser()
        token, _body = browser.csrf("/login")
        status, final_url, body = browser.request("/login", data={
            "csrf": token,
            "username": "demo",
            "password": "demo1234",
            "next_url": "/app/projects",
        })
        self.assertEqual(status, 200)
        self.assertTrue(final_url.endswith("/app/projects"))
        self.assertIn("데모 사용자님의 프로젝트", body)

        suffix = str(int(time.time() * 1000))
        project_name = f"통합 테스트 {suffix}"
        token_match = re.search(r'name="csrf" value="([^"]+)"', body)
        self.assertIsNotNone(token_match)
        token = token_match.group(1)
        status, project_url, body = browser.request("/app/projects", data={
            "csrf": token,
            "name": project_name,
            "description": "연관관계와 상태 변경 검증",
        })
        self.assertEqual(status, 200)
        self.assertRegex(project_url, r"/app/projects/\d+$")
        self.assertIn(project_name, body)
        self.assertIn("소유자 데모 사용자", body)
        project_id = int(project_url.rsplit("/", 1)[1])

        token = re.search(r'name="csrf" value="([^"]+)"', body).group(1)
        task_title = f"상태 전이 {suffix}"
        status, _url, body = browser.request(
            f"/app/projects/{project_id}/tasks",
            data={
                "csrf": token,
                "title": task_title,
                "description": "대기에서 완료까지 이동",
            },
        )
        self.assertEqual(status, 200)
        self.assertIn(task_title, body)
        self.assertIn("대기", body)
        task_match = re.search(r'action="/app/tasks/(\d+)/status"', body)
        self.assertIsNotNone(task_match)
        task_id = int(task_match.group(1))

        token = re.search(r'name="csrf" value="([^"]+)"', body).group(1)
        status, _url, body = browser.request(
            f"/app/tasks/{task_id}/status",
            data={"csrf": token, "new_status": "in_progress"},
        )
        self.assertEqual(status, 200)
        self.assertIn("대기 → 진행 중", body)

        token = re.search(r'name="csrf" value="([^"]+)"', body).group(1)
        status, _url, body = browser.request(
            f"/app/tasks/{task_id}/status",
            data={"csrf": token, "new_status": "completed"},
        )
        self.assertEqual(status, 200)
        self.assertIn("진행 중 → 완료", body)

        status, _url, body = browser.request(
            f"/app/projects/{project_id}?q={urllib.parse.quote(task_title)}&status=completed"
        )
        self.assertEqual(status, 200)
        self.assertIn(task_title, body)
        self.assertIn('value="completed" selected', body)

        status, _url, body = browser.request(
            "/app/projects",
            data={"csrf": "invalid", "name": "실패해야 함", "description": ""},
        )
        self.assertEqual(status, 403)
        self.assertIn("요청 검증에 실패했습니다", body)

        outsider = Browser()
        token, _body = outsider.csrf("/signup")
        status, _url, body = outsider.request("/signup", data={
            "csrf": token,
            "username": f"user_{suffix}",
            "display_name": "다른 사용자",
            "password": "safe-password-123",
        })
        self.assertEqual(status, 200)
        self.assertIn("다른 사용자님의 프로젝트", body)
        status, _url, body = outsider.request(f"/app/projects/{project_id}")
        self.assertEqual(status, 403)
        self.assertIn("접근할 권한이 없습니다", body)

        token, _body = browser.csrf(f"/app/projects/{project_id}")
        status, final_url, body = browser.request(
            "/logout", data={"csrf": token}
        )
        self.assertEqual(status, 200)
        self.assertTrue(final_url.endswith("/"))
        self.assertIn("안전하게 로그아웃되었습니다", body)
        status, final_url, _body = browser.request("/app/projects")
        self.assertIn("/login?next=/app/projects", final_url)

        status, _url, body = Browser().request("/auth/github")
        self.assertEqual(status, 503)
        self.assertIn("GitHub 로그인이 설정되지 않았습니다", body)

        status, _url, body = Browser().request("/does-not-exist")
        self.assertEqual(status, 404)
        self.assertIn("요청한 페이지를 찾을 수 없습니다", body)


if __name__ == "__main__":
    unittest.main(verbosity=2)
