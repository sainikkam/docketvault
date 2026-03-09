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
    from app.oauth.router import router as oauth_router
    from app.extraction.router import router as extraction_router
    from app.enrichment.router import router as enrichment_router
    from app.sharing.router import router as sharing_router
    from app.exports.router import router as exports_router
    from app.notifications.router import router as notifications_router
    from app.gmail.router import router as gmail_router

    app.include_router(auth_router, tags=["auth"])
    app.include_router(firms_router, tags=["firms"])
    app.include_router(matters_router, tags=["matters"])
    app.include_router(evidence_router, tags=["evidence"])
    app.include_router(oauth_router, tags=["oauth"])
    app.include_router(extraction_router, tags=["extraction"])
    app.include_router(enrichment_router, tags=["enrichment"])
    app.include_router(sharing_router, tags=["sharing"])
    app.include_router(exports_router, tags=["exports"])
    app.include_router(notifications_router, tags=["notifications"])
    app.include_router(gmail_router, tags=["gmail"])

    return app


app = create_app()
