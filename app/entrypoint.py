from pathlib import Path

from starlette.responses import FileResponse, HTMLResponse

from app.main import app as backend_app
from app.architecture_api import router as architecture_router


# Register the real warehouse-analysis APIs before application startup so the
# WarehouseModel metadata is also known when Base.metadata.create_all runs.
backend_app.include_router(architecture_router)

STATIC_DIR = Path(__file__).resolve().parent / "static"
INDEX_FILE = STATIC_DIR / "index.html"
ARCH_JS_FILE = STATIC_DIR / "warehouse-architecture.js"
API_FIX_JS_FILE = STATIC_DIR / "api-fix.js"
UI_TOAST_JS_FILE = STATIC_DIR / "ui-toast-position.js"
TASK_REFERENCE_JS_FILE = STATIC_DIR / "warehouse-task-reference.js"


class FrontendFirstApp:
    """Serve the product UI at / while preserving the FastAPI app and /docs."""

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            path = scope.get("path")
            if path in {"/", "/index.html"}:
                html = INDEX_FILE.read_text(encoding="utf-8")
                scripts = (
                    '<script src="/warehouse-architecture.js?v=4"></script>\n'
                    '<script src="/api-fix.js?v=2"></script>\n'
                    '<script src="/ui-toast-position.js?v=1"></script>\n'
                    '<script src="/warehouse-task-reference.js?v=1"></script>'
                )
                if '/warehouse-task-reference.js?v=1' not in html:
                    html = html.replace("</body>", scripts + "\n</body>")
                response = HTMLResponse(html)
                await response(scope, receive, send)
                return
            if path == "/warehouse-architecture.js":
                response = FileResponse(
                    ARCH_JS_FILE,
                    media_type="application/javascript; charset=utf-8",
                )
                await response(scope, receive, send)
                return
            if path == "/api-fix.js":
                response = FileResponse(
                    API_FIX_JS_FILE,
                    media_type="application/javascript; charset=utf-8",
                )
                await response(scope, receive, send)
                return
            if path == "/ui-toast-position.js":
                response = FileResponse(
                    UI_TOAST_JS_FILE,
                    media_type="application/javascript; charset=utf-8",
                )
                await response(scope, receive, send)
                return
            if path == "/warehouse-task-reference.js":
                response = FileResponse(
                    TASK_REFERENCE_JS_FILE,
                    media_type="application/javascript; charset=utf-8",
                )
                await response(scope, receive, send)
                return
        await backend_app(scope, receive, send)


app = FrontendFirstApp()
