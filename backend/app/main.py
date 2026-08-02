from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from .routers import auth_router, devices_router, logs_router
from .config import settings
from .services import device_service, firewall_service

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="NestNetController API",
    description="Family-friendly network firewall manager",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(devices_router)
app.include_router(logs_router)

@app.on_event("startup")
async def sync_allowlist_on_startup():
    """Ensure the firewall allowlist matches devices.yaml every time the app starts"""
    logger.info("Syncing device allowlist with devices.yaml...")
    all_devices = device_service.get_all_devices()
    firewall_service.sync_allowlist(all_devices)

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "NestNetController API",
        "version": "1.0.0",
        "dry_run": settings.dry_run,
        "wan_interface": settings.wan_interface,
        "lan_interface": settings.lan_interface
    }

@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "dry_run_mode": settings.dry_run,
        "interfaces": {
            "wan": settings.wan_interface,
            "lan": settings.lan_interface
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
