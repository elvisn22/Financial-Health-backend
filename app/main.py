from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.session import Base, engine
from app.routers import auth, assessments


def create_app() -> FastAPI:
    settings = get_settings()

    Base.metadata.create_all(bind=engine)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Financial Health Assessment API for SMEs",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router)
    app.include_router(assessments.router)

    @app.get("/health", tags=["system"])
    def health_check():
        return {"status": "ok"}

    return app


app = create_app()

