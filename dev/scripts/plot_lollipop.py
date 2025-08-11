#!/usr/bin/env python3
import argparse
import sys
import requests
from typing import List, Dict, Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import myvariant
import mygene


# ---------------------------
# MyVariant helpers
# ---------------------------

def mv_client() -> myvariant.MyVariantInfo:
    return myvariant.MyVariantInfo()


def mg_client() -> mygene.MyGeneInfo:
    return mygene.MyGeneInfo()


def hgvs_from_vcf(path: str) -> List[str]:
    """Use MyVariant's built-in VCF→HGVS converter (robust and build-agnostic)."""
    mv = mv_client()
    return list(mv.get_hgvs_from_vcf(path))


def format_hgvs_token(token: str) -> str:
    """
    Best-effort normalization for a free token.
    - If looks like valid HGVS already (contains ':g.' or ':c.' or startswith 'chr'), return as-is.
    - Else try parse as 'chrom pos ref alt' and build HGVS with client helper.
    """
    mv = mv_client()
    t = token.strip()
    if ':g.' in t or ':c.' in t or t.startswith('chr'):
        return t

    parts = t.replace(',', ' ').replace('\t', ' ').split()
    if len(parts) == 4:
        chrom, pos, ref, alt = parts[0], int(parts[1]), parts[2], parts[3]
        return mv.format_hgvs(chrom, pos, ref, alt)
    return t  # hope it's a valid HGVS already


def chunked(iterable, n):
    """Yield successive n-sized chunks from iterable."""
    for i in range(0, len(iterable)):
        if i % n == 0:
            yield iterable[i:i + n]


def fetch_variants_batch(hgvs_list: List[str], assembly: str) -> List[Dict[str, Any]]:
    """
    Batch-fetch variants from MyVariant.
    Returns only dict docs (filters out None).
    """
    if not hgvs_list:
        return []
    mv = mv_client()
    fields = [
        # gene & protein pos
        "dbnsfp.genename", "dbnsfp.aapos",
        # consequence
        "vep.consequence", "snpeff.ann.effect",
        # scores
        "cadd.phred",
        # clinvar significance
        "clinvar.rcv.clinical_significance.description",
        "clinvar.gene.symbol"
    ]
    out = []
    for batch in chunked(hgvs_list, 1000):
        #res = mv.getvariants(batch, fields=",".join(fields), assembly=assembly)
        res = mv.getvariants(batch, fields="all", assembly=assembly)
        #print(res)
        for r in res:
            if isinstance(r, dict):
                out.append(r)
    return out


# ---------------------------
# Parsing helpers
# ---------------------------

def parse_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize one MyVariant document to a row for plotting."""
    hgvs = doc.get("_id", "")

    # gene symbol (prefer dbNSFP for broad coverage)
    gene = (
        doc.get("dbnsfp", {}).get("genename")
        or doc.get("clinvar", {}).get("gene", {}).get("symbol")
        or "NA"
    )

    # protein position
    aapos = doc.get("dbnsfp", {}).get("aa", {}).get("pos")
    print(aapos)
    if isinstance(aapos, list):
        protein_pos = aapos[0]
    else:
        protein_pos = aapos

    # consequence (prefer VEP, fallback to snpEff)
    consequence = None
    vep_cons = doc.get("vep", {}).get("consequence")
    if isinstance(vep_cons, list) and vep_cons:
        consequence = vep_cons[0]
    elif isinstance(vep_cons, str):
        consequence = vep_cons
    else:
        ann = doc.get("snpeff", {}).get("ann", [])
        if ann and isinstance(ann, list) and isinstance(ann[0], dict):
            consequence = ann[0].get("effect")

    # CADD
    cadd = doc.get("cadd", {}).get("phred")

    # ClinVar significance
    clinvar_sig = None
    rcv = doc.get("clinvar", {}).get("rcv")
    if isinstance(rcv, list) and rcv:
        cs = rcv[0].get("clinical_significance", {})
        clinvar_sig = cs.get("description")

    return {
        "variant": hgvs,
        "gene": gene,
        "pos": protein_pos,
        "impact": consequence,
        "cadd": cadd,
        "clinvar": clinvar_sig,
    }


# ---------------------------
# UniProt domains
# ---------------------------

def map_gene_to_uniprot(gene_symbol: str) -> str:
    """Try to get a reviewed UniProt accession via MyGene."""
    if not gene_symbol or gene_symbol == "NA":
        return ""
    mg = mg_client()
    q = mg.query(f"symbol:{gene_symbol}", fields="uniprot.Swiss-Prot,uniprot.Swiss-Prot", species="human")
    if not q or "hits" not in q or not q["hits"]:
        return ""
    hit = q["hits"][0]
    sp = hit.get("uniprot", {}).get("Swiss-Prot")
    if isinstance(sp, list) and sp:
        return sp[0]
    if isinstance(sp, str):
        return sp
    return ""


def fetch_uniprot_features(uniprot_id: str) -> List[Dict[str, Any]]:
    """Fetch UniProt features JSON and return DOMAIN features."""
    if not uniprot_id:
        return []
    url = f"https://rest.uniprot.org/uniprotkb/{uniprot_id}.json"
    r = requests.get(url, timeout=20)
    if r.status_code != 200:
        return []
    data = r.json()
    feats = data.get("features", [])
    domains = []
    for f in feats:
        if f.get("type") == "DOMAIN":
            loc = f.get("location", {})
            try:
                start = int(loc["start"]["value"])
                end = int(loc["end"]["value"])
            except Exception:
                continue
            domains.append({
                "start": start,
                "end": end,
                "desc": f.get("description", "DOMAIN")
            })
    return domains


def add_domain_layers(fig: go.Figure, domains: List[Dict[str, Any]], y=0.15):
    """Overlay domain rectangles on the plot background."""
    for d in domains:
        fig.add_shape(
            type="rect",
            x0=d["start"],
            x1=d["end"],
            y0=y - 0.05,
            y1=y + 0.05,
            fillcolor="lightblue",
            opacity=0.5,
            line=dict(width=0),
            layer="below"
        )
        fig.add_annotation(
            x=(d["start"] + d["end"]) / 2,
            y=y + 0.08,
            text=d["desc"],
            showarrow=False,
            font=dict(size=10)
        )


# ---------------------------
# Plotting
# ---------------------------

CLINVAR_COLOR_MAP = {
    "Pathogenic": "#e74c3c",
    "Likely_pathogenic": "#e67e22",
    "Likely pathogenic": "#e67e22",
    "Benign": "#2ecc71",
    "Likely_benign": "#58d68d",
    "Likely benign": "#58d68d",
    "Uncertain_significance": "#7f8c8d",
    "Uncertain significance": "#7f8c8d",
}

def make_plot(
    df: pd.DataFrame,
    gene: str,
    output: str,
    color_by: str = "impact",
    size_by: str = "cadd",
    uniprot_id: str = "",
    draw_domains: bool = False,
    protein_length: int = None
):
    """
    color_by: 'impact' | 'clinvar' | 'cadd'
    size_by:  'cadd' | 'impact_count'
    """
    df = df.copy()

    # drop rows without protein position
    df = df[pd.notnull(df["pos"])]
    if df.empty:
        print("[!] Nothing to plot (no protein positions).")
        return

    # group-size visualization
    if size_by == "impact_count":
        counts = df["impact"].value_counts().to_dict()
        df["impact_count"] = df["impact"].map(counts)
        size_col = "impact_count"
    else:
        size_col = "cadd"

    # color logic
    color_kwargs = {}
    if color_by == "clinvar":
        # create a normalized group label column for legend
        def norm_sig(x):
            if x is None:
                return "Unknown"
            s = str(x).replace(" ", "_")
            # keep originals too for better matching
            return s
        df["clinvar_group"] = df["clinvar"].apply(norm_sig)
        # custom color map for legend
        color_kwargs["color"] = "clinvar_group"
        color_kwargs["color_discrete_map"] = {**CLINVAR_COLOR_MAP, "Unknown": "black"}
    elif color_by == "cadd":
        color_kwargs["color"] = "cadd"
        color_kwargs["color_continuous_scale"] = "Viridis"
    else:
        color_kwargs["color"] = "impact"

    # Build figure
    fig = px.scatter(
        df,
        x="pos",
        y=[1] * len(df),
        size=size_col,
        title=f"Lollipop Plot — {gene}",
        labels={"pos": "Protein position"},
        hover_data={
            "variant": True,
            "impact": True,
            "cadd": True,
            "clinvar": True,
            "pos": True
        },
        **color_kwargs
    )
    fig.update_traces(marker=dict(line=dict(width=1, color="rgba(40,40,40,0.6)")))
    fig.update_layout(
        yaxis=dict(visible=False),
        showlegend=True,
        width=1200,
        height=450,
        margin=dict(l=40, r=20, t=60, b=40),
    )
    if protein_length:
        fig.update_xaxes(range=[0, protein_length])

    # Optional: UniProt domains
    if draw_domains:
        domains = fetch_uniprot_features(uniprot_id) if uniprot_id else []
        if not domains and gene and not uniprot_id:
            mapped = map_gene_to_uniprot(gene)
            if mapped:
                domains = fetch_uniprot_features(mapped)
        if domains:
            add_domain_layers(fig, domains, y=0.15)

    fig.write_html(output)
    print(f"[✓] Plot saved → {output}")


# ---------------------------
# CLI
# ---------------------------

def main():
    p = argparse.ArgumentParser(description="Lollipop plot from MyVariant.info with optional UniProt domains.")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--vcf", help="Path to VCF file.")
    src.add_argument("--variants", nargs="+",
                     help="Variants as HGVS (e.g., 'chr17:g.7673803C>G' or transcript HGVS) "
                          "or tokens 'chrom pos ref alt' (e.g., '17 7673803 C G').")
    p.add_argument("--assembly", choices=["hg19", "hg38"], default="hg38",
                   help="Genome build for MyVariant queries (must match your HGVS coordinates).")
    p.add_argument("--output", default="lollipop_plot.html", help="Output HTML file.")
    p.add_argument("--color_by", choices=["impact", "clinvar", "cadd"], default="impact",
                   help="Color points by consequence, ClinVar significance, or CADD.")
    p.add_argument("--size_by", choices=["cadd", "impact_count"], default="cadd",
                   help="Size points by CADD or by number of variants with the same consequence.")
    p.add_argument("--gene", help="Gene symbol to display and/or to map UniProt ID (optional).")
    p.add_argument("--uniprot", help="UniProt accession (e.g., P04637) to overlay domains (optional).")
    p.add_argument("--domains", action="store_true", help="Overlay UniProt domain tracks.")
    p.add_argument("--protein_length", type=int, help="X-axis max (protein length).")
    args = p.parse_args()

    # build list of HGVS ids
    if args.vcf:
        hgvs_list = hgvs_from_vcf(args.vcf)
    else:
        hgvs_list = [format_hgvs_token(t) for t in args.variants]

    if not hgvs_list:
        print("[!] No variants to query after normalization.")
        sys.exit(1)

    print(f"[i] Querying {len(hgvs_list)} variants (assembly={args.assembly})...")
    docs = fetch_variants_batch(hgvs_list, assembly=args.assembly)
    #print(docs)

    rows = [parse_doc(d) for d in docs if isinstance(d, dict)]
    rows = [r for r in rows if r.get("pos") is not None]
    if not rows:
        print("[!] No variants with protein positions; nothing to plot.")
        sys.exit(0)

    df = pd.DataFrame(rows)

    # If no gene provided, use first non-NA
    gene = args.gene or (df["gene"][df["gene"] != "NA"].iloc[0] if (df["gene"] != "NA").any() else "NA")

    make_plot(
        df=df,
        gene=gene,
        output=args.output,
        color_by=args.color_by,
        size_by=args.size_by,
        uniprot_id=args.uniprot or "",
        draw_domains=args.domains,
        protein_length=args.protein_length
    )


if __name__ == "__main__":
    main()
