from pathlib import Path

from starlette.responses import FileResponse

from app.main import app as backend_app
from app.architecture_api import router as architecture_router


# Register the real warehouse-analysis APIs before application startup so the
# WarehouseModel metadata is also known when Base.metadata.create_all runs.
backend_app.include_router(architecture_router)

INDEX_FILE = Path(__file__).resolve().parent / "static" / "index.html"


class FrontendFirstApp:
    """Serve the product UI at / while preserving the FastAPI app and /docs."""

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http" and scope.get("path") in {"/", "/index.html"}:
            response = FileResponse(INDEX_FILE, media_type="text/html; charset=utf-8")
            await response(scope, receive, send)
            return
        await backend_app(scope, receive, send)


app = FrontendFirstApp()
