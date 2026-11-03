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


def csrf_from_html(body: str) -> str:
    match = re.search(r'name="csrf" value="([^"]+)"', body)
    if not match:
        raise AssertionError("CSRF token not found in response HTML")
    return match.group(1)


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
        return csrf_from_html(body), body


class FlowTaskIntegrationTest(unittest.TestCase):
    def test_stylesheet_preserves_public_https_origin(self) -> None:
        browser = Browser()
        status, _url, body = browser.request("/")
        self.assertEqual(status, 200)
        match = re.search(r'<link rel="stylesheet" href="([^"]+)"', body)
        self.assertIsNotNone(match)
        href = match.group(1)
        # A TLS proxy may forward HTTP internally; assets must keep the public origin.
        public_asset = urllib.parse.urlsplit(
            urllib.parse.urljoin("https://public.example/", href)
        )
        self.assertEqual(public_asset.scheme, "https")
        self.assertEqual(public_asset.netloc, "public.example")
        status, _url, stylesheet = browser.request(
            urllib.parse.urlunsplit(("", "", public_asset.path, public_asset.query, ""))
        )
        self.assertEqual(status, 200)
        self.assertIn(".hero", stylesheet)

    def test_expired_post_returns_to_project_list_after_login(self) -> None:
        browser = Browser()
        status, final_url, body = browser.request(
            "/app/tasks/1/status", data={"csrf": "expired", "new_status": "todo"}
        )
        self.assertEqual(status, 200)
        match = re.search(r'name="next_url" value="([^"]+)"', body)
        self.assertIsNotNone(match)
        status, final_url, _body = browser.request("/login", data={
            "csrf": csrf_from_html(body), "username": "demo", "password": "demo1234",
            "next_url": match.group(1),
        })
        self.assertEqual(status, 200)
        self.assertTrue(final_url.endswith("/app/projects"))

    def test_unicode_tokens_return_validation_errors(self) -> None:
        browser = Browser()
        browser.csrf("/login")
        status, _url, _body = browser.request("/login", data={
            "csrf": "한글", "username": "demo", "password": "demo1234",
        })
        self.assertEqual(status, 403)
        status, _url, _body = browser.request("/auth/github")
        self.assertEqual(status, 503)
        query = urllib.parse.urlencode({"code": "unused", "state": "한글"})
        status, _url, _body = browser.request(f"/auth/github/callback?{query}")
        self.assertEqual(status, 401)

    def test_oversized_passwords_return_form_errors(self) -> None:
        browser = Browser()
        for path, expected_status, extra in (
            ("/signup", 400, {"username": "oversized", "display_name": "길이 검사"}),
            ("/login", 401, {"username": "demo"}),
        ):
            with self.subTest(path=path):
                token, body = browser.csrf(path)
                status, _url, body = browser.request(path, data={
                    "csrf": token, "password": "x" * 4097, **extra,
                })
                self.assertEqual(status, expected_status)
                self.assertIn('class="form-error"', body)

    def test_non_bmp_password_can_be_entered_and_used_for_login(self) -> None:
        browser = Browser()
        token, body = browser.csrf("/signup")
        password_input = re.search(r'<input\b[^>]*\bname="password"[^>]*>', body)
        self.assertIsNotNone(password_input)
        self.assertNotIn("maxlength=", password_input.group(0))
        username = f"emoji_{time.time_ns()}"
        password = "😀" * 3000
        self.assertGreater(len(password.encode("utf-16-le")) // 2, 4096)
        status, _url, body = browser.request("/signup", data={
            "csrf": token, "username": username, "display_name": "유니코드 검사",
            "password": password,
        })
        self.assertEqual(status, 200)
        status, _url, _body = browser.request(
            "/logout", data={"csrf": csrf_from_html(body)}
        )
        self.assertEqual(status, 200)
        token, body = browser.csrf("/login")
        password_input = re.search(r'<input\b[^>]*\bname="password"[^>]*>', body)
        self.assertIsNotNone(password_input)
        self.assertNotIn("maxlength=", password_input.group(0))
        status, final_url, body = browser.request("/login", data={
            "csrf": token, "username": username, "password": password,
        })
        self.assertEqual(status, 200)
        self.assertTrue(final_url.endswith("/app/projects"))
        self.assertIn("유니코드 검사님의 프로젝트", body)

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
        self.assertNotEqual(token, csrf_from_html(body))

        suffix = str(int(time.time() * 1000))
        project_name = f"통합 테스트 {suffix}"
        token = csrf_from_html(body)
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

        token = csrf_from_html(body)
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

        token = csrf_from_html(body)
        status, _url, body = browser.request(
            f"/app/tasks/{task_id}/status",
            data={"csrf": token, "new_status": "in_progress"},
        )
        self.assertEqual(status, 200)
        self.assertIn("대기 → 진행 중", body)

        token = csrf_from_html(body)
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
        self.assertNotEqual(token, csrf_from_html(body))
        status, _url, body = outsider.request(f"/app/projects/{project_id}")
        self.assertEqual(status, 403)
        self.assertIn("접근할 권한이 없습니다", body)

        token, _body = outsider.csrf("/app/projects")
        for path, data in (
            (f"/app/projects/{project_id}/tasks", {"title": "침입", "description": ""}),
            (f"/app/tasks/{task_id}/status", {"new_status": "todo"}),
            (f"/app/tasks/{task_id}/delete", {}),
            (f"/app/projects/{project_id}/delete", {}),
        ):
            with self.subTest(unauthorized_path=path):
                status, _url, _body = outsider.request(path, data={"csrf": token, **data})
                self.assertEqual(status, 403)

        token, body = browser.csrf(f"/app/projects/{project_id}")
        self.assertIn("다시 열기", body)
        for new_status, message in (
            ("todo", "완료 → 대기"),
            ("in_progress", "대기 → 진행 중"),
            ("todo", "진행 중 → 대기"),
        ):
            status, _url, body = browser.request(
                f"/app/tasks/{task_id}/status",
                data={"csrf": token, "new_status": new_status},
            )
            self.assertEqual(status, 200)
            self.assertIn(message, body)
        status, _url, body = browser.request(
            f"/app/tasks/{task_id}/delete", data={"csrf": token}
        )
        self.assertEqual(status, 200)
        self.assertNotIn(task_title, body)
        status, final_url, body = browser.request(
            f"/app/projects/{project_id}/delete", data={"csrf": token}
        )
        self.assertEqual(status, 200)
        self.assertTrue(final_url.endswith("/app/projects"))
        self.assertNotIn(project_name, body)

        token = csrf_from_html(body)
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
