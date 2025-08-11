# app/gene_overview.py

from __future__ import annotations
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from mygene import MyGeneInfo

import httpx



router = APIRouter(prefix="/api/gene", tags=["gene"])
GNOMAD_URL = "https://gnomad.broadinstitute.org/api"


GQL = """
query Q($gene:String!,$ds:DatasetId!,$ref:ReferenceGenomeId!){
  gene(gene_symbol:$gene, reference_genome:$ref){
    gene_id symbol chrom start stop strand canonical_transcript_id
    variants(dataset:$ds){ variant_id rsid genome{ac an af} exome{ac an af} }
  }
}
"""


GQL_GENE_WITH_VARIANTS = """
query GeneVariants($geneSymbol: String!, $dataset: DatasetId!, $referenceGenome: ReferenceGenomeId!) {
  gene(gene_symbol: $geneSymbol, reference_genome: $referenceGenome) {
    gene_id
    symbol
    chrom
    start
    stop
    strand
    canonical_transcript_id
    variants(dataset: $dataset) {
      variant_id
      rsid
      genome { ac an af }
      exome  { ac an af }
    }
  }
}
"""

def _af(block: Optional[Dict[str, Any]]) -> Optional[float]:
    if not block:
        return None
    if block.get("af") is not None:
        return block["af"]
    ac, an = block.get("ac"), block.get("an")
    try:
        return (float(ac) / float(an)) if (ac is not None and an) else None
    except Exception:
        return None

def _pick_af(v: Dict[str, Any]) -> Optional[float]:
    e = v.get("exome") or {}
    g = v.get("genome") or {}
    ef = _af(e)
    return ef if ef is not None else _af(g)

def _to_hgvs_g(variant_id: Optional[str]) -> Optional[str]:
    if not variant_id:
        return None
    try:
        chrom, pos, ref, alt = variant_id.split("-")
        return f"chr{chrom}:g.{pos}{ref}>{alt}"
    except Exception:
        return variant_id

async def _fetch_gnomad_gene(gene: str, dataset: str, ref: str) -> Dict[str, Any]:
    payload = {
        "query": GQL_GENE_WITH_VARIANTS,
        "variables": {"geneSymbol": gene, "dataset": dataset, "referenceGenome": ref},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(GNOMAD_URL, json=payload, headers={"content-type": "application/json"})
    if r.status_code != 200:
        raise HTTPException(r.status_code, r.text)
    js = r.json()
    if "errors" in js:
        msg = js["errors"][0].get("message", "gnomAD error")
        raise HTTPException(502, msg)
    return js.get("data", {}).get("gene") or {}

def _normalize_variants(variants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for v in (variants or []):
        out.append({
            "rsid": (v.get("rsid") or "").strip(),
            "variant_id": v.get("variant_id"),
            "hgvs_g": _to_hgvs_g(v.get("variant_id")),
            "allele_frequency": _pick_af(v),
        })
    return out

# simple per-process cache to avoid hammering MyGene on refresh
_MG = MyGeneInfo()

def _mygene_summary(gene: str) -> Optional[str]:
    try:
        res = _MG.query(f"symbol:{gene}", species="human", fields="summary", size=1)
        hits = res.get("hits") or []
        return (hits[0].get("summary") if hits else None) or None
    except Exception:
        return None

@router.get("/overview")
async def overview(gene: str, dataset: str = "gnomad_r4", ref: str = "GRCh38"):
    dataset = dataset or "gnomad_r4"
    ref     = ref or "GRCh38"
    # 1) gnomAD gene & variants
    g = await _fetch_gnomad_gene(gene, dataset, ref)
    variants = _normalize_variants(g.get("variants") or [])

    # 2) MyGene summary
    summary = _mygene_summary(gene)

    return {
        "gene": g.get("symbol") or gene,
        "dataset": dataset,
        "ref": ref,
        "summary": summary,                         # <- MyGene summary
        "coordinates": {                            # <- gnomAD basics
            "gene_id": g.get("gene_id"),
            "chrom": g.get("chrom"),
            "start": g.get("start"),
            "stop": g.get("stop"),
            "strand": g.get("strand"),
            "canonical_transcript_id": g.get("canonical_transcript_id"),
        },
        "counts": {
            "variants_total": len(variants),
            "variants_with_af": sum(1 for v in variants if v.get("allele_frequency") is not None),
        },
        "variants": variants,                       # [{rsid, variant_id, hgvs_g, allele_frequency}]
    }



def pick_af(v):
    def af(block): 
        if not block: return None
        if block.get("af") is not None: return block["af"]
        ac, an = block.get("ac"), block.get("an")
        return (float(ac)/float(an)) if (ac is not None and an) else None
    return af(v.get("exome")) if af(v.get("exome")) is not None else af(v.get("genome"))

def hgvs_g(variant_id):
    try:
        chrom,pos,ref,alt = variant_id.split("-")
        return f"chr{chrom}:g.{pos}{ref}>{alt}"
    except Exception:
        return variant_id

