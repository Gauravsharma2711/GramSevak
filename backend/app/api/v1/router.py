from fastapi import APIRouter
from backend.app.api.v1.endpoints import health, panchayats, forecast, advisory, officer, farmer, location, notification

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(health.router, prefix="", tags=["Health"])
api_router.include_router(panchayats.router, prefix="", tags=["Panchayats"])
api_router.include_router(forecast.router, prefix="", tags=["Forecasts"])
api_router.include_router(advisory.router, prefix="", tags=["Advisories"])
api_router.include_router(officer.router, prefix="", tags=["Officer Review"])
api_router.include_router(farmer.router, prefix="", tags=["Farmer Services"])
api_router.include_router(location.router, prefix="", tags=["Location Intelligence"])
api_router.include_router(notification.router, prefix="", tags=["Farmer Notifications"])




