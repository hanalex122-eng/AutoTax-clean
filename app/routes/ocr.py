from fastapi import APIRouter, UploadFile, File, HTTPException, Body, Request
from fastapi.concurrency import run_in_threadpool
from typing import List
import os

from app.services.image_processor import to_raw_png, prepare_for_ocr
from app.services.ocr_engine import run_ocr
from app.services.invoice_parser import parse_invoice
from app.services.amount_parser import extract_total_amount
from app.services.invoice_db import (
    add_invoice, update_invoice, get_review_queue, get_invoice,
    find_duplicate, find_recurring
)
from app.services.qr_reader import read_qr, parse_qr
from app.models.invoice import InvoiceResult
from app.services.user_db import check_quota, increment_usage, PLANS

router = APIRouter(prefix="/ocr", tags=["OCR"])

MAX_FILE_SIZE = 30 * 1024 * 1024  # 30 MB

ALLOWED_EXT = {
    ".jpg", ".jpeg", ".png", ".webp",
    ".bmp", ".tiff", ".tif", ".pdf"
}

QR_MAX_STR = 500
QR_MAX_TOTAL = 9_999_999


def _sanitize_filename(name: str) -> str:
    base = os.path.basename(name or "upload")
    safe = "".join(c for c in base if c.isalnum() or c in "._- ")
    return safe[:120] or "upload"


def _sanitize_qr_override(qr: dict) -> dict:
    safe = {}
    for k, v in qr.items():
        if k == "raw":
            continue
        if not isinstance(v, str):
            v = str(v)
        v = v.strip()[:200]
        if k == "total":
            try:
                f = float(v.replace(",", "."))
                if 0 < f <= QR_MAX_TOTAL:
                    safe[k] = f
            except ValueError:
                pass
        elif k == "vat_rate":
            try:
                i = int(v)
                if 0 < i <= 30:
                    safe[k] = i
            except ValueError:
                pass
        elif k in (
            "date", "time", "invoice_number",
            "vendor", "company", "vat_amount"
        ):
            safe[k] = v
    return safe


def _plan_allows_qr(user) -> bool:
    if not user:
        return False
    plan = user.get("plan", "free")
    return PLANS.get(plan, PLANS["free"]).get("qr", False)


async def _process(
    f: UploadFile,
    qr_allowed: bool = True,
    user_id: str = None
) -> InvoiceResult:

    filename = _sanitize_filename(f.filename or "upload")

    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(
            status_code=415,
            detail=f"Desteklenmeyen dosya türü: {ext}"
        )

    raw = await f.read()
    if len(raw) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Dosya çok büyük. Maksimum 30 MB."
        )

    if len(raw) < 100:
        raise HTTPException(
            status_code=400,
            detail="Dosya boş veya bozuk."
        )

    raw_png = await run_in_threadpool(to_raw_png, raw, filename)

    qr_raw = (
        await run_in_threadpool(read_qr, raw_png)
        if qr_allowed else None
    )
    qr_parsed = (
        _sanitize_qr_override(parse_qr(qr_raw))
        if qr_raw else {}
    )

    ocr_ready = await run_in_threadpool(prepare_for_ocr, raw_png)
    text = await run_in_threadpool(run_ocr, ocr_ready)

    parsed = parse_invoice(text)

    # 🔥 Çok dilli gelişmiş total extractor
    better_total = extract_total_amount(text)
    if better_total is not None:
        parsed["total"] = better_total

    # QR override
    for key in (
        "total", "date", "time",
        "invoice_number", "vendor",
        "vat_amount", "vat_rate", "company"
    ):
        if qr_parsed.get(key) is not None:
            parsed[key] = qr_parsed[key]

    needs_review = not parsed.get("total")
    review_reason = (
        "Toplam tutar bulunamadı"
        if needs_review else None
    )

    inv_id = add_invoice(parsed, filename, user_id)

    return InvoiceResult(
        invoice_id=inv_id,
        filename=filename,
        vendor=parsed.get("vendor"),
        date=parsed.get("date"),
        time=parsed.get("time"),
        total=parsed.get("total"),
        vat_rate=parsed.get("vat_rate"),
        vat_amount=parsed.get("vat_amount"),
        invoice_no=parsed.get("invoice_number"),
        category=parsed.get("category"),
        payment_method=parsed.get("payment_method"),
        qr_raw=qr_raw[:QR_MAX_STR] if qr_raw else None,
        qr_parsed=qr_parsed or None,
        raw_text=text[:5000],
        needs_review=needs_review,
        review_reason=review_reason,
        message="OCR tamamlandı",
    )


@router.post("/upload", response_model=InvoiceResult)
async def upload(request: Request, file: UploadFile = File(...)):
    user = getattr(request.state, "user", None)

    if not user:
        raise HTTPException(status_code=401, detail="Giriş gerekli.")

    allowed, used, limit = check_quota(user)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Aylık fatura limitinize ulaştınız."
        )

    result = await _process(
        file,
        qr_allowed=_plan_allows_qr(user),
        user_id=user["id"]
    )

    increment_usage(user["id"])
    return result

@router.get("/review-queue")
def review_queue(request: Request, page: int = 1, per_page: int = 50):
    user = getattr(request.state, "user", None)

    if not user:
        raise HTTPException(status_code=401, detail="Giriş gerekli.")

    return get_review_queue(user["id"], page=page, per_page=per_page)

@router.get("/invoice/{inv_id}")
def get_one(request: Request, inv_id: str):
    user = getattr(request.state, "user", None)

    if not user:
        raise HTTPException(status_code=401, detail="Giriş gerekli.")

    inv = get_invoice(inv_id, user["id"])

    if not inv:
        raise HTTPException(status_code=404, detail="Fatura bulunamadı.")

    return inv


@router.patch("/invoice/{inv_id}")
def patch_invoice(request: Request, inv_id: str, fields: dict = Body(...)):
    user = getattr(request.state, "user", None)

    if not user:
        raise HTTPException(status_code=401, detail="Giriş gerekli.")

    ok = update_invoice(inv_id, user["id"], fields)

    if not ok:
        raise HTTPException(
            status_code=404,
            detail="Fatura bulunamadı veya güncellenemedi."
        )

    return {"status": "ok", "invoice_id": inv_id}