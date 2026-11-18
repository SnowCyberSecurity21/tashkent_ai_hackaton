"""Mezon FastAPI app: API routers + static web app."""
from __future__ import annotations

import logging
import sys

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, func, select

from . import config, llm
from .db import get_session, init_db
from .models import AuditLog, Document, Product, SafetyRule, Scan
from .routers import admin, approvals, maker, patient, products, reports, safety, scan

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
app = FastAPI(title="Mezon API", version="0.1.0")
# vendored JS (bwip-js ~1 MB, Tailwind ~450 KB) shrinks 3-5x: matters for phones on slow venue networks
app.add_middleware(GZipMiddleware, minimum_size=1024)

for r in (scan, products, patient, safety, approvals, reports, maker, admin):
    app.include_router(r.router)


@app.on_event("startup")
def _startup() -> None:
    sys.path.insert(0, str(config.ROOT))
    init_db()
    from scripts.seed import seed_if_empty

    if seed_if_empty():
        logging.getLogger("mezon").info("Bo'sh baza: demo ma'lumotlar yuklandi")


@app.exception_handler(RequestValidationError)
async def _validation(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": "Ma'lumot noto'g'ri yuborildi. Maydonlarni tekshiring.",
                                                  "errors": exc.errors()[:3]}, )


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    logging.getLogger("mezon").exception("Unhandled error")
    return JSONResponse(status_code=500, content={"detail": "Serverda kutilmagan xatolik. Birozdan keyin qayta urinib ko'ring."})


@app.get("/api/health")
def health(session: Session = Depends(get_session)):
    last_reset = session.exec(select(AuditLog.ts).where(AuditLog.action == "demo.reset").order_by(AuditLog.id.desc()).limit(1)).first()
    return {
        "ok": True, "demo_mode": config.DEMO_MODE, "llm": llm.status(),
        "demo_reset_at": last_reset.isoformat(timespec="seconds") if last_reset else None,
        "counts": {
            "products": session.exec(select(func.count()).select_from(Product)).one(),
            "scans": session.exec(select(func.count()).select_from(Scan)).one(),
            "rules_approved": session.exec(select(func.count()).select_from(SafetyRule).where(SafetyRule.approved == True)).one(),  # noqa: E712
        },
    }


@app.get("/api/documents/{doc_id}/file")
def document_file(doc_id: int, session: Session = Depends(get_session)):
    doc = session.get(Document, doc_id)
    if not doc or not doc.path or not doc.verified:
        raise HTTPException(404, "Hujjat topilmadi")
    path = (config.ROOT / doc.path).resolve()
    if config.DATA_DIR.resolve() not in path.parents or not path.exists():
        raise HTTPException(404, "Hujjat fayli topilmadi")
    return FileResponse(path, media_type="application/pdf", filename=path.name)


app.mount("/", StaticFiles(directory=str(config.WEB_DIR), html=True), name="web")
