# 경로와 접근 정책

## 공개·보호 경로 정책

| HTTP | 경로 | 정책 | 설명 |
| --- | --- | --- | --- |
| `GET` | `/` | 공개 | 로그인 상태에 따라 메뉴와 시작 버튼이 달라지는 홈 |
| `GET`, `POST` | `/login` | 공개 | 로그인 화면과 인증 처리 |
| `GET`, `POST` | `/signup` | 공개 | 회원가입 화면과 계정 생성 |
| `GET` | `/auth/github` | 공개 | GitHub OAuth 인증 시작 |
| `GET` | `/auth/github/callback` | 공개 | OAuth state 검증과 로그인 완료 |
| `GET` | `/health` | 공개 | 서버 상태 확인 |
| `GET` | `/docs`, `/redoc`, `/openapi.json` | 공개 | FastAPI 자동 API 문서 |
| `POST` | `/logout` | 보호 | 세션 제거와 로그아웃 |
| 모든 메서드 | `/app/**` | 보호 | 프로젝트·할 일 기능 |

비로그인 사용자는 보호 화면 대신 로그인 화면으로 이동한다. 로그인한 사용자도 다른 사용자의 프로젝트와 할 일에는 접근할 수 없다.

## 주요 기능 경로

| 기능 | HTTP | 경로 |
| --- | --- | --- |
| 프로젝트 목록·검색 | `GET` | `/app/projects?q=검색어` |
| 프로젝트 생성 | `POST` | `/app/projects` |
| 프로젝트와 연결된 할 일 조회 | `GET` | `/app/projects/{project_id}` |
| 할 일 검색·필터 | `GET` | `/app/projects/{project_id}?q=검색어&status=completed` |
| 할 일 생성 | `POST` | `/app/projects/{project_id}/tasks` |
| 할 일 상태 변경 | `POST` | `/app/tasks/{task_id}/status` |
| 할 일 삭제 | `POST` | `/app/tasks/{task_id}/delete` |
| 프로젝트와 자식 할 일 삭제 | `POST` | `/app/projects/{project_id}/delete` |
