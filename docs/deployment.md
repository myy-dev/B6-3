# 환경 변수와 배포

[README로 돌아가기](../README.md)

## 환경 변수

지원하는 변수의 예시는 [.env.example](../.env.example)에 있다. 애플리케이션은 프로세스 환경 변수를 읽으므로, 로컬에서는 셸에서 설정하고 배포 환경에서는 서비스의 환경 변수 설정에 등록한다.

| 변수 | 용도 | 로컬 기본값 |
| --- | --- | --- |
| `APP_SECRET_KEY` | 세션 쿠키 서명 | 개발용 기본값 |
| `DATABASE_URL` | SQLAlchemy 연결 URL | `sqlite:///./database.db` |
| `SESSION_HTTPS_ONLY` | HTTPS에서만 세션 쿠키 전송 | `false` |
| `GITHUB_CLIENT_ID` | GitHub OAuth App ID | 미설정 |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth App 비밀값 | 미설정 |

운영 또는 공유 환경에서는 `APP_SECRET_KEY`를 긴 무작위 값으로 설정하고 배포 간 유지한다.

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

출력된 값을 Render의 `APP_SECRET_KEY`에 등록한다. 값을 변경하면 기존 세션이 무효화된다. `SESSION_HTTPS_ONLY`는 Render에서 `true`, 로컬 HTTP 개발에서는 `false`를 사용한다.

## GitHub 소셜 로그인 설정

1. GitHub의 **Settings → Developer settings → OAuth Apps**에서 OAuth App을 생성한다.
2. 배포용 앱의 주소를 아래와 같이 지정한다.

| 항목 | 배포용 입력값 |
| --- | --- |
| Application name | `FlowTask` |
| Homepage URL | `https://b6-3.onrender.com` |
| Authorization callback URL | `https://b6-3.onrender.com/auth/github/callback` |

3. 앱의 Client ID를 확인하고 Client secret을 발급한다.
4. Render 웹 서비스의 **Environment**에서 `GITHUB_CLIENT_ID`와 `GITHUB_CLIENT_SECRET`을 추가하고 저장·재배포한다.
5. 공개 서비스에서 **GitHub로 계속하기**를 눌러 계정 승인을 완료하고 프로젝트 화면으로 돌아오는지 확인한다.

로컬 개발은 별도 OAuth App을 사용하고 콜백 URL을 `http://127.0.0.1:8000/auth/github/callback`으로 지정한다. 다른 포트로 실행하면 콜백 URL도 같은 포트로 맞춘다. 로컬 환경 변수 설정 예시는 다음과 같다.

```bash
export GITHUB_CLIENT_ID='...'
export GITHUB_CLIENT_SECRET='...'
uvicorn main:app --reload
```

기존 OAuth App을 계속 사용한다면 Homepage URL과 Authorization callback URL을 위 Render 주소로 변경한다.

클라이언트 비밀값은 Render 환경 변수에 직접 입력하며 문서나 저장소에 기록하지 않는다.

## Render 배포

무료 웹 서비스와 기존 SQLite를 사용한다. 영구 디스크와 외부 DB는 연결하지 않는다.

| 항목 | 값 |
| --- | --- |
| 공개 주소 | <https://b6-3.onrender.com/> |
| 상태 확인 | <https://b6-3.onrender.com/health> |
| 배포 브랜치 | `main` |

2026-11-07 공개 주소에서 기본 응답과 데모 로그인·세션 유지·로그아웃을 확인했다. 상세 결과와 확인 범위는 [테스트와 검증](testing.md#공개-서버-검증)에 정리했다.

### Blueprint로 생성

1. 배포할 코드와 [render.yaml](../render.yaml)을 GitHub 저장소에 반영한다.
2. Render에서 **New → Blueprint**를 선택하고 `myy-dev/B6-3` 저장소와 변경사항이 반영된 브랜치를 연결한다.
3. `render.yaml`의 무료 웹 서비스 설정을 확인하고 배포한다. Python 버전은 저장소의 `.python-version`을 사용한다.
4. 배포 완료 후 서비스의 실제 `onrender.com` 주소와 `/health` 응답을 확인한다.
5. GitHub 로그인을 사용하려면 위 OAuth 설정을 적용하고 실제 계정으로 로그인·새로고침 후 세션 유지를 확인한다.

Blueprint는 `APP_SECRET_KEY`를 자동 생성한다. GitHub OAuth 변수는 서비스 생성 후 Environment에서 별도로 입력한다.

### 대시보드에서 직접 생성

**New → Web Service**에서 같은 저장소와 배포 브랜치를 연결하고 다음 값을 지정한다.

| 항목 | 설정 |
| --- | --- |
| Language | Python 3 |
| Instance Type | Free |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/health` |

Environment에 아래 값을 등록한다. `PORT`는 Render에서 제공하므로 별도로 지정하지 않는다.

| 환경 변수 | 배포 설정 |
| --- | --- |
| `DATABASE_URL` | `sqlite:///./database.db` |
| `APP_SECRET_KEY` | 배포 간 유지할 긴 무작위 비밀값 |
| `SESSION_HTTPS_ONLY` | `true` |
| `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` | GitHub 소셜 로그인을 사용할 경우 발급받은 값 |

### 데이터 저장과 접속

SQLite 파일은 서비스의 임시 파일시스템에 저장된다. 서버 재시작·재배포·절전 복귀 시 회원·프로젝트·할 일 데이터가 초기화될 수 있다. 초기화 후에는 애플리케이션 시작 시 테이블과 데모 계정이 다시 생성된다. 이 배포는 데이터 초기화를 허용하는 과제 시연용 구성이다.

무료 웹 서비스는 15분 동안 요청이 없으면 절전 상태로 전환되며, 다음 접속 시 기동 시간이 걸릴 수 있다.

설정 방법은 [Render FastAPI 배포 안내](https://render.com/docs/deploy-fastapi), [Blueprint 설정](https://render.com/docs/blueprint-spec), [무료 서비스 제한](https://render.com/docs/free)을 참고한다.
