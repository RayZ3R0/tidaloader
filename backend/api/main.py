import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

# Load env before imports that might need it
load_dotenv()

# Fix path to include backend root
sys.path.append(str(Path(__file__).parent.parent))

from api.routers import system, troi, search, downloads, library
from api.clients import tidal_client
from api.utils.logging import log_warning, log_info
from download_state import download_state_manager
from queue_manager import queue_manager, QUEUE_AUTO_PROCESS

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    tidal_client.cleanup_old_status_cache()
    download_state_manager._cleanup_old_entries()
    
    # Initialize queue manager and start processing if auto mode is enabled
    log_info(f"Queue manager initialized: auto_process={QUEUE_AUTO_PROCESS}")
    if QUEUE_AUTO_PROCESS:
        # Start queue processing in background
        import asyncio
        asyncio.create_task(queue_manager.start_processing())
        log_info("Queue auto-processing started")
    
    yield
    # Shutdown
    await queue_manager.stop_processing()

app = FastAPI(title="Tidaloader API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(system.router)
app.include_router(troi.router)
app.include_router(search.router)
app.include_router(downloads.router)
app.include_router(library.router)

# Frontend Serving
frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"

if frontend_dist.exists():
    assets_path = frontend_dist / "assets"
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        if full_path.startswith("api"):
            raise HTTPException(status_code=404, detail="Not found")
        
        index_path = frontend_dist / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return {"message": "Frontend not found"}
else:
    log_warning("Frontend dist folder not found. Run 'npm run build' in frontend directory.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)