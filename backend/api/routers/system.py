from fastapi import APIRouter

router = APIRouter()

@router.get("/api")
async def api_root():
    return {"status": "ok", "message": "Tidaloader API"}

@router.get("/api/health")
async def health_check():
    return {"status": "healthy"}
