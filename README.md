# 로그인이 되고 회원끼리 연결되는 웹 서비스 만들기

## 프로젝트 개요

FastAPI와 SQLAlchemy를 사용해 사용자 인증·인가, 모델 연관관계와 할 일 상태 변경 기능을 갖춘 웹 서비스를 구현하는 프로젝트

## 기술 스택

| 구분 | 기술 |
| --- | --- |
| 언어 | Python 3.10 이상, 로컬 검증 3.14.5 |
| 웹 프레임워크 | FastAPI 0.116.1 |
| ASGI 서버 | Uvicorn 0.35.0 |
| ORM | SQLAlchemy 2.0.41 |
| 데이터베이스 | SQLite |
| 서버 템플릿 | Jinja2 3.1.6 |
| 화면 구성 | HTML, CSS |
| 폼 데이터 파싱 | python-multipart 0.0.20 |
| 세션 쿠키 서명 | Starlette SessionMiddleware, itsdangerous 2.2.0 |
| 비밀번호 해싱 | passlib 1.7.4, PBKDF2-SHA256 |

## 프로젝트 구조

```text
B6-3/
├── .github/workflows/test.yml   # 컴파일·도메인·저장소·HTTP 통합 검사
├── .env.example                # 환경 변수 예시
├── .gitignore
├── README.md
├── requirements.txt            # 직접 의존성과 버전
├── Procfile                    # 배포 서버 실행 명령
├── database.db                 # 최초 실행 시 생성되는 SQLite 파일, Git 제외
├── main.py                     # 앱 생성, 미들웨어, 라우터 등록, 전역 예외 처리
├── config.py                   # 환경 변수 설정
├── database.py                 # 엔진, 세션, ORM Base, 테이블 생성, SQLite FK 활성화
├── exceptions.py               # 인증·인가·도메인 예외
├── ui.py                       # Jinja2 공통 컨텍스트, 알림, 스타일시트 버전 관리
├── auth/                       # 인증·인가와 OAuth
│   ├── dependencies.py         # Depends 기반 사용자 조회와 로그인 필수 검사
│   ├── security.py             # 세션 시작, CSRF, 로그인 후 이동 경로 검증
│   └── oauth.py                # GitHub 인증 요청과 사용자 정보 조회
├── routers/                    # 요청 수신, 서비스 호출, SSR 응답과 리다이렉트
│   ├── web.py
│   ├── auth.py
│   └── projects.py
├── services/                   # 입력 검증, 소유권 검사, 상태 전이 비즈니스 로직
│   ├── auth_service.py
│   ├── project_service.py
│   └── task_service.py
├── repositories/               # SQLAlchemy 기반 데이터 접근
│   ├── user_repository.py
│   ├── project_repository.py
│   └── task_repository.py
├── models/                     # ORM 모델과 양방향 1:N 연관관계
│   ├── user.py
│   ├── project.py
│   └── task.py
├── templates/                  # Jinja2 SSR 화면
│   ├── base.html
│   ├── home.html
│   ├── login.html
│   ├── signup.html
│   ├── error.html
│   └── projects/
│       ├── index.html
│       └── detail.html
├── static/
│   └── styles.css              # 데스크톱·모바일 반응형 스타일
├── tests/
│   ├── domain_checks.py        # 인증·관계·상태 전이·삭제 정책 검사
│   ├── repository_checks.py    # 저장소·동시 요청·SQLite 호환성 회귀 검사
│   └── integration_smoke.py    # 실행 중인 서버의 HTTP 사용자 흐름 검사
└── docs/
    ├── architecture.md         # 계층 구조, 인증·인가, 모델 관계, 상태 변경, 보안
    ├── authentication.md       # 테스트 계정과 인증 방식
    ├── routes.md               # 공개·보호 정책과 주요 기능 경로
    ├── testing.md              # 테스트 실행과 기존 검증 기록
    ├── deployment.md           # 환경 변수, GitHub OAuth, Railway 영구 볼륨 배포
    ├── screenshots.md          # 실행 화면 자료
    └── screenshots/
```

## 실행

저장소 루트에서 실행한다.

### macOS / Linux

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

브라우저에서 <http://127.0.0.1:8000>에 접속한다. 최초 실행 시 `database.db`, 테이블과 테스트 계정이 자동 생성된다. 다른 포트가 필요하면 실행 명령에 `--port 8001`처럼 지정한다.

테스트 계정은 [테스트 계정과 인증 방식](docs/authentication.md), 환경 변수와 외부 서비스 설정은 [환경 변수와 배포](docs/deployment.md), 검사 명령은 [테스트와 검증](docs/testing.md)을 참고한다.

## 수행 항목 체크리스트

### 개발 환경 준비

- [x] Python 3.10 이상 사용
- [x] 가상환경 생성·활성화와 패키지 설치 방법 작성
- [x] `requirements.txt`에 주요 패키지 버전 명시
- [x] FastAPI 서버 실행과 브라우저 접속 확인

### 프로젝트 구조

- [x] `auth/`, `routers/`, `services/`, `repositories/`, `models/`, `templates/` 구성
- [x] 인증·인가, 요청·응답, 비즈니스 규칙, 데이터 접근, 화면 역할 분리
- [x] 애플리케이션 시작과 전역 설정을 별도 파일로 구성

### 인증

- [x] FastAPI `Depends` 기반 인증 구현
- [x] 세션 기반 인증 방식 선택과 이유 작성
- [x] 로그인 성공·실패 결과 안내
- [x] 로그인 성공 시 세션에 사용자 식별자 저장
- [x] 로그아웃 시 세션 제거
- [x] DB 테스트 계정 자동 생성과 [인증 문서에 ID/PW 명시](docs/authentication.md)
- [x] 인증 의존성을 `auth/` 모듈로 분리

### 접근 제어와 UI

- [x] 비로그인 사용자의 핵심 기능 접근 차단
- [x] 비로그인 보호 경로 접근 시 로그인 화면으로 이동
- [x] [공개·보호 경로 정책](docs/routes.md)을 표로 문서화
- [x] 로그인 전에는 로그인·회원가입 버튼 표시
- [x] 로그인 후에는 사용자 이름·로그아웃·프로젝트 이동 메뉴 표시
- [x] 프로젝트와 할 일의 사용자별 소유권 검사

### 도메인 모델과 연관관계

- [x] `User`, `Project`, `Task` 모델 3개 구성
- [x] `User → Project` 1:N 관계 구현
- [x] `Project → Task` 1:N 관계 구현
- [x] `relationship`과 `back_populates`로 양방향 관계 구현
- [x] 프로젝트 목록에 연관된 할 일 수 표시
- [x] 상세 화면에 프로젝트 소유자와 할 일 목록 표시
- [x] 부모 삭제 시 자식 삭제 정책과 선택 이유를 코드 주석으로 명시
- [x] N:M 관계 미사용

### 데이터 저장

- [x] 모든 핵심 데이터를 SQLAlchemy ORM과 SQLite에 저장
- [x] 외래 키와 연관관계를 DB 기준으로 조회
- [x] FastAPI `Depends`로 DB 세션 전달
- [x] 요청 종료 시 DB 세션 정리

### 상태 변경 비즈니스 기능

- [x] 대기 → 진행 중 → 완료 상태 전이 구현
- [x] 진행 중 → 대기, 완료 → 대기 전이 구현
- [x] 허용되지 않은 상태 변경을 서비스 계층에서 차단
- [x] 상태 변경 전·후를 알림 메시지와 카드 표시로 구분

### 화면 흐름과 SSR

- [x] 주요 화면을 Jinja2 `TemplateResponse`로 렌더링
- [x] 공통 레이아웃과 템플릿 컨텍스트 구성
- [x] 로그인 → 핵심 기능 → 생성·조회 → 상태 변경 → 결과 확인 흐름 연결
- [x] 데이터 변경 성공 후 HTTP 303으로 GET 화면에 이동
- [x] 데스크톱·모바일 반응형 화면 구성

### 제출물

- [x] 전체 소스코드 [GitHub 저장소](https://github.com/myy-dev/B6-3) 구성
- [x] Python·주요 패키지 버전 명시
- [x] 가상환경·설치·실행 방법 명시
- [x] [테스트 계정과 인증 방식 선택 이유](docs/authentication.md) 문서화
- [x] [공개·보호 경로 정책 표와 주요 기능 경로 목록](docs/routes.md) 작성
- [x] 선택 사항인 주요 화면 스크린샷 포함

## 보너스 과제

### 전역 예외 처리

- [x] 커스텀 예외와 FastAPI 전역 예외 처리기 구현
- [x] 없는 데이터·권한 없는 접근 등 실패 상황을 공통 화면으로 안내

### 검색과 필터

- [x] 프로젝트 이름·설명 검색
- [x] 할 일 제목·설명 검색과 상태 필터
- [x] 검색 결과 없음 안내와 필터 초기화 제공

### OAuth2 소셜 로그인

- [x] GitHub OAuth2 Authorization Code Flow 구현
- [x] OAuth state 검증과 GitHub 계정 기반 사용자 연결
- [ ] 실제 GitHub 계정과 배포 주소를 통한 최종 로그인 확인

### 비밀번호 해싱과 회원가입

- [x] 사용자 회원가입과 아이디 중복 검사
- [x] 비밀번호 해시 저장과 로그인 시 검증
- [x] 닉네임·아이디·비밀번호 입력값 검증

### 외부 배포

- [x] 환경 변수 기반 실행 설정과 배포 시작 명령 구성
- [x] Railway 웹 서비스·SQLite 영구 볼륨 배포 절차 문서화
- [ ] Railway에 실제 배포하고 외부 접속 URL 제출

## 제약 사항

- Python 3.10 이상을 사용한다.
- 핵심 패키지는 FastAPI, Uvicorn, SQLAlchemy, Jinja2, python-multipart를 사용한다.
- 인증 패키지는 과제에서 허용한 passlib, itsdangerous, Starlette 범위에서 사용한다.
- 허용 범위 밖의 외부 라이브러리를 추가하지 않는다. OAuth HTTP 통신은 표준 라이브러리를 사용한다.
- 모든 핵심 데이터는 SQLAlchemy ORM과 관계형 DB에 저장한다.
- 모델은 최소 3개, 1:N 또는 N:1 관계는 최소 2개, 양방향 관계는 최소 1개를 구성한다.
- 직접적인 N:M 관계는 사용하지 않는다.
- 인증·인가, 도메인, 데이터 접근, 화면 처리의 역할을 분리한다.
- 복잡한 다단계 역할 권한 체계는 요구하지 않는다.
- 주요 화면은 Jinja2 기반 SSR로 출력한다.
- 소셜 로그인과 외부 배포는 선택 보너스이며 실제 검증 완료 여부를 별도로 표시한다.

## 결과물

- [테스트 계정과 인증 방식](docs/authentication.md): 데모 계정, 세션 인증 선택 이유, 비밀번호 저장 방식
- [경로와 접근 정책](docs/routes.md): 공개·보호 경로 정책과 주요 기능 경로
- [서비스 구조와 동작](docs/architecture.md): 인증·인가 흐름, 모델 관계, 상태 전이, 보안 설계, 학습 목표
- [테스트와 검증](docs/testing.md): 검사 실행 방법, SQLite 호환성, 기존 QA 기록
- [환경 변수와 배포](docs/deployment.md): 로컬·운영 환경 설정, GitHub OAuth, Railway 영구 볼륨
- [화면 자료](docs/screenshots.md): 홈·프로젝트 상세·모바일 실행 화면
