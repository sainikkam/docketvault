from fastapi import FastAPI
from app.config import Settings

settings = Settings()


def create_app() -> FastAPI:
    app = FastAPI(title="DocketVault", version="0.1.0")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    from app.auth.router import router as auth_router
    from app.firms.router import router as firms_router
    from app.matters.router import router as matters_router
    from app.evidence.router import router as evidence_router

    app.include_router(auth_router, tags=["auth"])
    app.include_router(firms_router, tags=["firms"])
    app.include_router(matters_router, tags=["matters"])
    app.include_router(evidence_router, tags=["evidence"])

    return app


app = create_app()
