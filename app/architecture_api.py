from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.code_index import CodeIndexService
from app.db import get_db
from app.warehouse_analysis import WarehouseAnalysisService


router = APIRouter(prefix="/api/warehouse", tags=["Warehouse Architecture"])


@router.post("/scan")
def scan_warehouse(db: Session = Depends(get_db)):
    index = CodeIndexService(db).rebuild()
    result = WarehouseAnalysisService(db).scan()
    result["index"] = index
    result["message"] = "已基于 DolphinScheduler 本地 SQL 重新识别数仓分层、主题域和主题"
    return result


@router.get("/overview")
def warehouse_overview(db: Session = Depends(get_db)):
    return WarehouseAnalysisService(db).overview()


@router.get("/domains")
def warehouse_domains(db: Session = Depends(get_db)):
    return WarehouseAnalysisService(db).domains()


@router.get("/models")
def warehouse_models(
    layer: str | None = Query(None),
    domain: str | None = Query(None),
    subject: str | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    return WarehouseAnalysisService(db).models(layer=layer, domain=domain, subject=subject, q=q, limit=limit)


@router.get("/models/{model_id}")
def warehouse_model(model_id: int, db: Session = Depends(get_db)):
    result = WarehouseAnalysisService(db).model(model_id)
    if not result:
        raise HTTPException(404, "数仓模型不存在")
    return result


@router.get("/lineage")
def warehouse_lineage(table: str, db: Session = Depends(get_db)):
    return WarehouseAnalysisService(db).lineage(table)
