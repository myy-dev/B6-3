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
APP_SECRET_KEY='replace-with-a-random-secret' uvicorn main:app
```

## GitHub 소셜 로그인 설정

1. GitHub의 **Settings → Developer settings → OAuth Apps**에서 OAuth App을 생성한다.
2. 로컬 개발의 Authorization callback URL을 `http://127.0.0.1:8000/auth/github/callback`으로 지정한다.
3. 발급받은 값을 환경 변수로 설정한다.

```bash
export GITHUB_CLIENT_ID='...'
export GITHUB_CLIENT_SECRET='...'
uvicorn main:app --reload
```

배포 환경에서는 콜백 URL을 `https://서비스주소/auth/github/callback`으로 변경한다. 클라이언트 비밀값은 저장소에 커밋하지 않는다.

GitHub OAuth 흐름은 구현돼 있으나 실제 외부 계정과 배포 주소를 통한 최종 확인은 남아 있다.

## Railway 배포

Railway 웹 서비스 하나에 영구 볼륨을 연결해 SQLite 데이터를 보존한다. 실제 외부 배포는 아직 완료하지 않았다.

1. Railway에서 GitHub 저장소 `myy-dev/B6-3`를 연결한다.
2. 빌드 명령은 `pip install -r requirements.txt`, 시작 명령은 `uvicorn main:app --host 0.0.0.0 --port $PORT`로 설정한다. 같은 실행 명령이 `Procfile`에도 정의돼 있다.
3. 웹 서비스에 볼륨을 추가하고 마운트 경로를 `/data`로 지정한다.
4. 아래 환경 변수를 설정하고 상태 확인 경로를 `/health`로 지정한다.

| 환경 변수 | 배포 설정 |
| --- | --- |
| `DATABASE_URL` | `sqlite:////data/database.db` |
| `APP_SECRET_KEY` | 배포 간 유지할 긴 무작위 비밀값 |
| `SESSION_HTTPS_ONLY` | `true` |
| `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` | GitHub 소셜 로그인을 사용할 경우 발급받은 값 |

볼륨에 연결된 `/data` 아래에 DB를 저장해야 재시작·재배포 후에도 데이터가 유지된다. 로컬 개발에서는 기존 `sqlite:///./database.db` 설정을 사용한다. 배포 후 공개 도메인을 생성하고 GitHub OAuth App의 콜백 URL을 `https://서비스주소/auth/github/callback`으로 지정한다. 비밀값은 저장소에 커밋하지 않는다.

설정 방법은 [Railway FastAPI 배포 안내](https://docs.railway.com/guides/fastapi)와 [영구 볼륨 안내](https://docs.railway.com/volumes/reference)를 참고한다.
