from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app.core.config import settings
from app.core.security import create_test_token
from app.core.telemetry import setup_telemetry
from app.api.router import api_router

setup_telemetry()

app = FastAPI(
    title=settings.app_name,
    description="영양제 추천 서비스 - 복용 기록 마이크로서비스",
    version="1.0.0",
    docs_url="/docs" if settings.app_env == "development" else None,
    redoc_url="/redoc" if settings.app_env == "development" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
FastAPIInstrumentor.instrument_app(app)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "code": f"HTTP_{exc.status_code}",
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": True,
            "message": "요청 데이터가 올바르지 않습니다.",
            "code": "VALIDATION_ERROR",
        },
    )


@app.get("/health", tags=["헬스체크"])
async def health_check():
    return {"status": "ok", "service": settings.app_name}


@app.get("/dev/token/{cognito_id}", tags=["개발용"])
async def get_dev_token(cognito_id: str):
    """개발/테스트용 JWT 토큰 발급"""
    if settings.app_env != "development":
        return {"error": "운영 환경에서는 사용할 수 없습니다."}
    token = create_test_token(cognito_id)
    return {"access_token": token, "token_type": "bearer"}
