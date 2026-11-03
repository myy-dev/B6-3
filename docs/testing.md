# 테스트와 검증

[README로 돌아가기](../README.md)

## 도메인 검사

```bash
.venv/bin/python tests/domain_checks.py
.venv/bin/python tests/repository_checks.py
```

다음을 실제 SQLite DB에서 확인한다.

- 비밀번호 해시 저장
- `User → Project → Task` 두 개의 1:N 관계
- 허용·차단되는 상태 전이
- 사용자 삭제 시 프로젝트와 할 일 cascade 삭제
- ID 재사용과 동시 요청에서 소유권·상태 전이 보호
- 커밋 후 다른 사용자 데이터가 반환되지 않는지 검사
- 프로젝트 목록의 연관 작업 조회에서 소유권 재검사
- `RETURNING`을 지원하지 않는 SQLite 모드에서 생성·조회·변경·삭제

저장소는 SQLite 3.35의 `RETURNING` 구문에 의존하지 않는다. 실제 SQLite **3.34.1**과 **3.53.1**에서 도메인 11개, 저장소 회귀 4개, HTTP 통합 5개 검사를 각각 통과했다.

## HTTP 통합 검사

서버를 실행한 상태에서 다음 명령을 사용한다.

```bash
FLOWTASK_BASE_URL=http://127.0.0.1:8000 \
  .venv/bin/python tests/integration_smoke.py
```

익명 접근 차단, 로그인 성공·실패, 회원가입, 사용자별 인가, 프로젝트·할 일 생성, 상태 변경, 검색·필터, CSRF, 로그아웃, OAuth 미설정 오류, 404를 검증한다.

GitHub Actions는 push와 pull request마다 컴파일, 도메인·저장소 회귀 검사, HTTP 통합 검사를 실행한다. 브라우저 QA 결과와 증거 화면은 `.gstack/qa-reports/`에 저장되며 2026-07-28 기준 점수는 **100/100**이다.

## 실행 시 유의 사항

- 명령은 저장소 루트에서 실행한다. 가상환경이 활성화돼 있다면 `.venv/bin/python` 대신 `python`을 사용할 수 있다.
- 도메인·저장소 검사는 각각 임시 SQLite DB를 사용한다.
- HTTP 통합 검사는 대상 서버에 테스트용 계정·프로젝트·할 일을 생성하고 변경하므로 별도의 테스트 서버와 DB를 사용한다.
- 다른 포트로 실행했다면 `FLOWTASK_BASE_URL`도 같은 주소로 변경한다.
- 위 SQLite 버전별 결과와 2026-07-28 QA 점수는 기존 검증 기록이다. `.gstack/`는 로컬 검사 산출물이며 Git 추적 대상에서 제외돼 있다.
- 제출용 화면 자료는 [화면 자료 문서](screenshots.md)에 정리돼 있다.

## 공개 서버 검증

2026-11-03 [Railway 공개 서버](https://flowtask-production-b5b4.up.railway.app/)에서 HTTP 통합 검사로 기본 사용자 흐름을 검증했다. 브라우저에서도 데모 로그인, 프로젝트·할 일 생성, 대기 → 진행 중 → 완료 상태 변경을 확인했다. HTTPS 프록시 뒤에서 스타일 파일이 공개 사이트의 HTTPS 주소로 로드되는지 확인하는 회귀 검사도 포함한다. GitHub 소셜 로그인은 미설정 오류 처리까지만 확인했으며 실계정 로그인 검증은 남아 있다.
