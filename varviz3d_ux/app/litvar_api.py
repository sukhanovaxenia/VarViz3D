# app/litvar_api.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import requests
from typing import List, Dict

router = APIRouter(prefix="/api/litvar", tags=["litvar"])

UA = {"User-Agent": "variant-viz/1.0 (+you@example.com)", "Accept": "application/json"}
LITVAR_RS2PMIDS = "https://www.ncbi.nlm.nih.gov/research/bionlp/litvar/api/v1/public/rsids2pmids"

class RsidBatch(BaseModel):
    rsids: List[str]

def _normalize_counts(data) -> Dict[str, int]:
    out: Dict[str, int] = {}
    if isinstance(data, dict):
        for rsid, pmids in data.items():
            out[str(rsid).lower()] = len(pmids or [])
    elif isinstance(data, list):
        for entry in data:
            if isinstance(entry, dict):
                rsid = (entry.get("rsid") or "").lower()
                pmids = entry.get("pmids", []) or []
                if rsid:
                    out[rsid] = len(pmids)
    return out

def _chunks(xs, n):
    for i in range(0, len(xs), n):
        yield xs[i:i+n]

@router.post("/pmid_counts")
def pmid_counts(body: RsidBatch):
    items = [r.strip().lower() for r in body.rsids if r and r.strip()]
    if not items:
        raise HTTPException(400, "No RSIDs provided")

    # LitVar tolerates decent batch sizes; keep it conservative (e.g., 150-200)
    agg: Dict[str, int] = {}
    for chunk in _chunks(items, 150):
        r = requests.get(LITVAR_RS2PMIDS, params={"rsids": ",".join(chunk)}, headers=UA, timeout=30)
        if not r.ok:
            raise HTTPException(r.status_code, r.text[:200])
        piece = _normalize_counts(r.json())
        agg.update(piece)

    # ensure all keys present
    for rs in items:
        agg.setdefault(rs, 0)

    return {"counts": agg}
