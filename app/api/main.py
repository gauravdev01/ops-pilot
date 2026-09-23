from fastapi import FastAPI

from app.api.routes.jd import router as jd_router
from app.api.routes.job_match import router as job_match_router
from app.api.routes.resume import router as resume_router
from app.api.routes.resume_tailor import router as resume_tailor_router
from app.core.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name, debug=settings.debug)
app.include_router(jd_router)
app.include_router(job_match_router)
app.include_router(resume_router)
app.include_router(resume_tailor_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}
