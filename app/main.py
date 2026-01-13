"""Main FastAPI application."""
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import logging

from .config import settings
from .database import get_db, init_db
from .api import events, subscriptions, auth

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Monthly newsletter of upcoming events in London",
    debug=settings.debug
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
# app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates/web")


# Include API routers
app.include_router(events.router, prefix="/api/events", tags=["events"])
app.include_router(subscriptions.router, prefix="/api/subscriptions", tags=["subscriptions"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])


@app.on_event("startup")
async def startup_event():
    """Initialize app on startup."""
    logger.info(f"Starting {settings.app_name}")
    logger.info(f"Environment: {settings.app_env}")

    # Initialize database
    try:
        init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down application")


@app.get("/")
async def root(request: Request):
    """Landing page."""
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "title": settings.app_name}
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": "0.1.0",
        "environment": settings.app_env
    }


@app.get("/api/sources")
async def list_sources(db: Session = Depends(get_db)):
    """List all data sources and their status."""
    from .models.database import DataSource
    sources = db.query(DataSource).all()
    return {
        "sources": [
            {
                "name": s.name,
                "type": s.source_type,
                "enabled": s.is_enabled,
                "last_successful_fetch": s.last_successful_fetch,
                "events_count": s.events_fetched_count,
                "success_rate": s.success_rate,
                "last_error": s.last_error
            }
            for s in sources
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
