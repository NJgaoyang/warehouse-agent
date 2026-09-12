from pathlib import Path

from starlette.responses import FileResponse

from app.main import app as backend_app


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
