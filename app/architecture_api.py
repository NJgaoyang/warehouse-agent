import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.code_index import CodeIndexService
from app.db import get_db
from app.warehouse_analysis import WarehouseAnalysisService


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/warehouse", tags=["Warehouse Architecture"])


def _internal_error(operation: str, exc: Exception) -> HTTPException:
    logger.exception("warehouse api failed: %s", operation)
    return HTTPException(
        status_code=500,
        detail={
            "operation": operation,
            "error_type": exc.__class__.__name__,
            "message": str(exc) or repr(exc),
        },
    )


@router.post("/scan")
def scan_warehouse(db: Session = Depends(get_db)):
    try:
        index = CodeIndexService(db).rebuild()
        result = WarehouseAnalysisService(db).scan()
        result["index"] = index
        result["message"] = "已基于 DolphinScheduler 本地 SQL 重新识别数仓分层、主题域和主题"
        return result
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise _internal_error("scan", exc)


@router.get("/overview")
def warehouse_overview(db: Session = Depends(get_db)):
    try:
        return WarehouseAnalysisService(db).overview()
    except Exception as exc:
        raise _internal_error("overview", exc)


@router.get("/domains")
def warehouse_domains(db: Session = Depends(get_db)):
    try:
        return WarehouseAnalysisService(db).domains()
    except Exception as exc:
        raise _internal_error("domains", exc)


@router.get("/models")
def warehouse_models(
    layer: str | None = Query(None),
    domain: str | None = Query(None),
    subject: str | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    try:
        return WarehouseAnalysisService(db).models(
            layer=layer,
            domain=domain,
            subject=subject,
            q=q,
            limit=limit,
        )
    except Exception as exc:
        raise _internal_error("models", exc)


@router.get("/models/{model_id}")
def warehouse_model(model_id: int, db: Session = Depends(get_db)):
    try:
        result = WarehouseAnalysisService(db).model(model_id)
        if not result:
            raise HTTPException(404, "数仓模型不存在")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise _internal_error(f"model:{model_id}", exc)


@router.get("/models/{model_id}/detail")
def warehouse_model_detail(model_id: int, db: Session = Depends(get_db)):
    """Return model + lineage in one request for the architecture UI."""
    try:
        service = WarehouseAnalysisService(db)
        model = service.model(model_id)
        if not model:
            raise HTTPException(404, "数仓模型不存在")
        lineage = service.lineage(model["qualified_name"])
        return {
            "model": model,
            "lineage": lineage,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise _internal_error(f"model_detail:{model_id}", exc)


@router.get("/lineage")
def warehouse_lineage(table: str, db: Session = Depends(get_db)):
    try:
        return WarehouseAnalysisService(db).lineage(table)
    except Exception as exc:
        raise _internal_error(f"lineage:{table}", exc)


@router.get("/diagnostics")
def warehouse_diagnostics(db: Session = Depends(get_db)):
    """Lightweight checks for field debugging on a deployed VM."""
    try:
        service = WarehouseAnalysisService(db)
        overview = service.overview()
        sample = service.models(limit=1)
        detail = None
        if sample:
            detail = service.model(sample[0]["id"])
            service.lineage(sample[0]["qualified_name"])
        return {
            "success": True,
            "overview_ok": True,
            "models_ok": True,
            "detail_ok": detail is not None if sample else True,
            "sample_model": sample[0]["qualified_name"] if sample else None,
            "total_tables": overview.get("total_tables", 0),
        }
    except Exception as exc:
        raise _internal_error("diagnostics", exc)
