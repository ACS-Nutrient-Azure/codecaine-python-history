from fastapi import APIRouter
from app.api.endpoints.records import router as records_router

api_router = APIRouter(prefix="/api")
api_router.include_router(records_router)
