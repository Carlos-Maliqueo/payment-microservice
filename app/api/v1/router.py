from fastapi import APIRouter
from app.api.v1.endpoints import payments, health

api_router = APIRouter()
api_router.include_router(payments.router)
api_router.include_router(health.router)