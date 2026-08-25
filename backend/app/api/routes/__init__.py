from fastapi import APIRouter

from app.api.routes import jobs, predictions, projects, results, upload

api_router = APIRouter()
api_router.include_router(upload.router)
api_router.include_router(jobs.router)
api_router.include_router(results.router)
api_router.include_router(projects.router)
api_router.include_router(predictions.router)
