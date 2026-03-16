# History 서비스

영양제 복용 기록과 구매 이력을 관리하는 FastAPI 마이크로서비스.
`intake_supplements` 테이블은 AWS DMS로 mypage `current_supplements`에서 CDC 동기화되어 읽기 전용으로 운영된다.

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| 언어 | Python 3.11 |
| 프레임워크 | FastAPI |
| ORM | SQLAlchemy 2.0 (async) + asyncpg |
| DB | PostgreSQL (`vitamin_history` DB) |
| 인증 | AWS Cognito (RS256 JWT / dev HS256 fallback) |

---

## 실행

```bash
cd services/history

# 가상환경 생성
python3.11 -m venv .venv
source .venv/bin/activate

# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
# .env 값 입력

# 서버 시작
uvicorn app.main:app --host 0.0.0.0 --port 8004 --reload
```

---

## 환경변수 (`.env`)

```env
# PostgreSQL
DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>:5432/vitamin_history

# AWS Cognito (JWT 검증용)
COGNITO_USER_POOL_ID=<User Pool ID>
COGNITO_CLIENT_ID=<App Client ID>
AWS_REGION=ap-northeast-2

# 개발용 JWT fallback (Cognito 미설정 시 HS256 사용)
JWT_SECRET_KEY=dev-secret-key
JWT_ALGORITHM=HS256
```

---

## 프로젝트 구조

```
app/
├── main.py                    # FastAPI 앱 + 라우터 등록
├── api/
│   ├── router.py              # 라우터 집계
│   └── endpoints/
│       └── records.py         # 복용 기록 엔드포인트
├── core/
│   ├── config.py              # pydantic-settings 환경변수
│   └── security.py            # JWT 검증 (Cognito RS256 / dev HS256 fallback)
├── db/
│   └── database.py            # async SQLAlchemy 엔진 + 세션
├── models/                    # ORM 모델
├── schemas/
│   └── history.py             # Pydantic 요청/응답 스키마
└── services/
    └── record_service.py      # 복용 기록 비즈니스 로직
```

---

## API 엔드포인트

| 메서드 | 경로 | 인증 | 설명 |
|--------|------|------|------|
| `GET` | `/health` | ❌ | 헬스체크 |
| `GET` | `/dev/token/{cognito_id}` | ❌ | 개발용 JWT 발급 |
| `GET` | `/api/history/supplements` | ✅ | 복용 영양제 목록 (DMS 동기화 데이터) |
| `GET` | `/api/history/records` | ✅ | 월별 복용 기록 조회 |
| `POST` | `/api/history/records` | ✅ | 복용 기록 추가/수정 (upsert) |

### `GET /api/history/supplements`

**Query Params** `cognito_id`, `is_active` (optional: `true` / `false`)

```json
{
  "supplements": [
    {
      "current_id": 1,
      "cognito_id": "string",
      "itk_product_name": "string",
      "itk_serving_per_day": 2,
      "itk_total_quantity": 60,
      "is_active": true,
      "remaining_count": 45,
      "low_stock": false
    }
  ]
}
```

### `GET /api/history/records`

**Query Params** `cognito_id`, `year`, `month`

```json
{
  "year": 2024,
  "month": 1,
  "records": [
    {
      "date": "2024-01-01",
      "supplements": [
        { "current_id": 1, "product_name": "string", "taken_count": 1, "daily_limit": 2 }
      ]
    }
  ]
}
```

### `POST /api/history/records`

`taken_count` 값에 맞게 `intake_item` row를 upsert한다.
잔여량이 10회분 이하로 떨어지면 재구매 알림 이벤트를 발행한다.

```json
// Request
{
  "cognito_id": "string",
  "current_id": 1,
  "date": "2024-01-01",
  "taken_count": 1
}
// Response: 204 No Content
```

---

## DB 스키마

`db-sql/historyTable.sql` 참고.

| 테이블 | 설명 |
|--------|------|
| `intake_supplements` | mypage `current_supplements`에서 DMS CDC 동기화 (읽기 전용) |
| `intake_item` | 영양제 1회 복용 기록 (1 row = 1회 복용) |
| `purchase_history` | 구매 이력 |

---

## 데이터 동기화 (AWS DMS)

`intake_supplements`는 mypage `current_supplements`의 CDC(Change Data Capture) 복제본이다.
history 서비스는 이 테이블에 직접 쓰지 않고, DMS가 자동으로 동기화한다.

> **현재 상태**: DMS 설정 미완료. 로컬 개발 환경에서는 mypage DB에서 직접 데이터를 삽입하거나 mock 데이터를 사용한다.
