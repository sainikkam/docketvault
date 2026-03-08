from fastapi import FastAPI
from app.config import Settings

settings = Settings()


def create_app() -> FastAPI:
    app = FastAPI(title="DocketVault", version="0.1.0")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    from app.auth.router import router as auth_router

    app.include_router(auth_router, tags=["auth"])

    return app


app = create_app()
