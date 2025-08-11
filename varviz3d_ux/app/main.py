from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
from gene_info import router as gene_info_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from litvar_api import router as litvar_router


import os

BASE_DIR = Path(__file__).resolve().parent.parent  # root of your project
FRONTEND_DIR = BASE_DIR / "frontend"


try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from pipeline import rsid_answer

app = FastAPI(title="Variant Viz API", version="0.1.0")

app.include_router(gene_info_router)
app.include_router(litvar_router)

# CORS (adjust origins in prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RsidDetailResponse(BaseModel):
    rsid: str
    gene: Optional[str] = None
    abstract_count: int
    sampled_pmids: int
    functional_answer: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/api/rsids/{rsid}/detail", response_model=RsidDetailResponse)
def rsid_detail(
    rsid: str,
    gene: Optional[str] = Query(None, description="Gene hint"),
    variant_hint: Optional[str] = Query(None, description="Variant aliases/regex"),
    sample: int = Query(10, ge=1, le=50),
):
    os.environ["SAMPLE_PMIDS"] = str(sample)
    out = rsid_answer(rsid, gene_hint=gene, variant_hint=variant_hint)
    return RsidDetailResponse(**out)

# print("Serving frontend from:", FRONTEND_DIR)


# API routes
from gene_overview import router as gene_overview_router
# from .gnomad_proxy import router as gnomad_router  # optional, if you already added it
from pipeline import rsid_answer  # if you have RSID detail route elsewhere

app.include_router(gene_overview_router)
# app.include_router(gnomad_router)  # optional

# register routers
from gene_overview import router as gene_overview_router
app.include_router(gene_overview_router)

# serve frontend (optional)
BASE_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = (BASE_DIR / "frontend").resolve()
if FRONTEND_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
    @app.get("/")
    def root():
        return RedirectResponse("/ui/")
