from fastapi import FastAPI


def create_app(db_path: str | None = None, provider_factory=None) -> FastAPI:
    app = FastAPI(title="X Archive")

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    return app
