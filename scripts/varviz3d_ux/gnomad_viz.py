# path: scripts/gnomad_clinvar_gene_view_fixed.py
"""
Gene summary HTML report (Ensembl + gnomAD + ClinVar via gnomAD region track)
- ClinVar: stacked histogram by clinical significance (Path/Uncertain/Benign/Other) with buttons.
- Gene structure: transcript labels moved to the RIGHT in a separate column, bigger font.
- All genomic plots share the same x-domain and unified margins for perfect vertical alignment.
- HTML is no-cache; output file has a timestamp suffix to bust browser cache.
- NEW: optional user-provided genomic coordinate marked by a black vertical line on all genomic plots.
"""

from __future__ import annotations

import html
from datetime import datetime
from typing import Any, Dict, List, Optional
import time

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objs as go
import requests

ENSEMBL_REST = "https://rest.ensembl.org"
HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}
GNOMAD_GRAPHQL = "https://gnomad.broadinstitute.org/api"

# ---------- Ensembl ----------
def lookup_gene(symbol: str, species: str = "homo_sapiens") -> Dict[str, Any]:
    url = f"{ENSEMBL_REST}/lookup/symbol/{species}/{symbol}?expand=1"
    r = requests.get(url, headers=HEADERS, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"Ensembl lookup error {r.status_code}: {r.text}")
    return r.json()


def get_transcript_xrefs(transcript_id: str) -> List[Dict[str, Any]]:
    url = f"{ENSEMBL_REST}/xrefs/id/{transcript_id}"
    r = requests.get(url, headers=HEADERS, timeout=10)
    if r.status_code != 200:
        return []
    return r.json()


def build_gene_summary(gj: Dict[str, Any]) -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "display_name": gj.get("display_name"),
        "ensembl_gene_id": gj.get("id"),
        "assembly": gj.get("assembly_name", "GRCh38"),
        "chrom": gj.get("seq_region_name"),
        "start": int(gj.get("start")),
        "end": int(gj.get("end")),
    }
    info["region"] = f'{info["chrom"]}:{info["start"]}-{info["end"]}'
    transcripts = []
    for t in gj.get("Transcript", []) or []:
        transcripts.append(
            {
                "id": t.get("id"),
                "display_name": t.get("display_name") or t.get("id"),
                "is_canonical": t.get("is_canonical", False),
                "start": int(t.get("start")),
                "end": int(t.get("end")),
                "exons": [
                    {
                        "start": int(e.get("start")),
                        "end": int(e.get("end")),
                        "id": e.get("id"),
                    }
                    for e in (t.get("Exon", []) or [])
                ],
            }
        )
    info["transcripts"] = transcripts
    return info


def annotate_transcripts(transcripts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for tx in transcripts:
        xrefs = get_transcript_xrefs(tx["id"])
        nm = [x["display_id"] for x in xrefs if x.get("display_id", "").startswith("NM_")]
        tx["refseq_mrna"] = nm
        tx["mane_candidate"] = bool(nm) and tx.get("is_canonical", False)
    return transcripts


# ---------- gnomAD & ClinVar (via gnomAD region track) ----------
def fetch_gnomad_variants_with_retry(
    chrom: str,
    start: int,
    stop: int,
    referenceGenome: str = "GRCh38",
    dataset: str = "gnomad_r4",
    max_retries: int = 3
) -> List[Dict[str, Any]]:
    """Fetch gnomAD variants with retry logic and better error handling"""
    
    query = """
    query($chrom: String!, $start: Int!, $stop: Int!, $referenceGenome: ReferenceGenomeId!, $dataset: DatasetId!) {
      region(chrom: $chrom, start: $start, stop: $stop, reference_genome: $referenceGenome) {
        variants(dataset: $dataset) {
          variantId chrom pos ref alt consequence genome { af }
        }
      }
    }"""
    
    variables = {
        "chrom": chrom,
        "start": int(start),
        "stop": int(stop),
        "referenceGenome": referenceGenome,
        "dataset": dataset,
    }
    
    for attempt in range(max_retries):
        try:
            r = requests.post(
                GNOMAD_GRAPHQL, 
                json={"query": query, "variables": variables}, 
                timeout=420  # Increased timeout
            )
            
            if r.status_code == 429:  # Rate limited
                wait_time = min(60, 2 ** attempt)
                print(f"Rate limited. Waiting {wait_time}s...")
                time.sleep(wait_time)
                continue
                
            data = r.json()
            if "errors" in data:
                print(f"gnomAD GraphQL error: {data['errors']}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return []
                
            return data.get("data", {}).get("region", {}).get("variants") or []
            
        except requests.Timeout:
            print(f"Timeout on attempt {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                time.sleep(5)
                continue
            return []
            
        except Exception as e:
            print(f"Error fetching gnomAD data: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return []
    
    return []

def fetch_gnomad_variants(
    chrom: str,
    start: int,
    stop: int,
    referenceGenome: str = "GRCh38",
    dataset: str = "gnomad_r4",
) -> List[Dict[str, Any]]:
    query = """
    query($chrom: String!, $start: Int!, $stop: Int!, $referenceGenome: ReferenceGenomeId!, $dataset: DatasetId!) {
      region(chrom: $chrom, start: $start, stop: $stop, reference_genome: $referenceGenome) {
        variants(dataset: $dataset) {
          variantId chrom pos ref alt consequence genome { af }
        }
      }
    }"""
    variables = {
        "chrom": chrom,
        "start": int(start),
        "stop": int(stop),
        "referenceGenome": referenceGenome,
        "dataset": dataset,
    }
    r = requests.post(GNOMAD_GRAPHQL, json={"query": query, "variables": variables}, timeout=420)
    data = r.json()
    if "errors" in data:
        raise RuntimeError(f"gnomAD GraphQL error: {data['errors']}")
    return data.get("data", {}).get("region", {}).get("variants") or []


def variants_to_dataframe(variants: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for v in variants:
        af = float((v.get("genome") or {}).get("af") or 0.0)
        rows.append(
            {
                "variantId": v.get("variantId"),
                "chrom": v.get("chrom"),
                "pos": int(v.get("pos")) if v.get("pos") is not None else None,
                "ref": v.get("ref"),
                "alt": v.get("alt"),
                "af": af,
                "consequence": v.get("consequence") or "unknown",
            }
        )
    return pd.DataFrame(rows)


def fetch_clinvar_variants(
    chrom: str,
    start: int,
    stop: int,
    referenceGenome: str = "GRCh38",
) -> List[Dict[str, Any]]:
    """ClinVar via gnomAD region track. If empty, returns []."""
    query = """
    query($chrom: String!, $start: Int!, $stop: Int!, $referenceGenome: ReferenceGenomeId!) {
      region(chrom: $chrom, start: $start, stop: $stop, reference_genome: $referenceGenome) {
        clinvar_variants {
          variant_id chrom pos ref alt clinical_significance review_status
        }
      }
    }"""
    variables = {
        "chrom": chrom,
        "start": int(start),
        "stop": int(stop),
        "referenceGenome": referenceGenome,
    }
    try:
        r = requests.post(GNOMAD_GRAPHQL, json={"query": query, "variables": variables}, timeout=420)
        data = r.json()
        if "errors" in data:
            print(data)
            return []
        return data.get("data", {}).get("region", {}).get("clinvar_variants") or []
    except Exception:
        return []


def clinvar_variants_to_dataframe(variants: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for v in variants:
        cs = (v.get("clinical_significance") or "unknown").lower()
        if any(k in cs for k in ["pathogenic", "likely pathogenic"]):
            sig_bucket = "Pathogenic / likely pathogenic"
        elif any(k in cs for k in ["uncertain", "conflicting"]):
            sig_bucket = "Uncertain significance / conflicting"
        elif any(k in cs for k in ["benign", "likely benign"]):
            sig_bucket = "Benign / likely benign"
        else:
            sig_bucket = "Other"

        cons = (v.get("consequence") or "").lower()
        if any(k in cons for k in ["stop_gained", "frameshift", "splice", "start_lost", "stop_lost"]):
            effect_bucket = "pLoF"
        elif "missense" in cons or "inframe" in cons:
            effect_bucket = "Missense / Inframe indel"
        elif "synonymous" in cons:
            effect_bucket = "Synonymous"
        else:
            effect_bucket = "Other"

        rows.append(
            {
                "variantId": v.get("variantId") or v.get("variant_id"),
                "chrom": v.get("chrom"),
                "pos": int(v.get("pos")) if v.get("pos") is not None else None,
                "ref": v.get("ref"),
                "alt": v.get("alt"),
                "clinical_significance": v.get("clinical_significance"),
                "review_status": v.get("review_status"),
                "effect_bucket": effect_bucket,
                "sig_bucket": sig_bucket,
            }
        )
    return pd.DataFrame(rows)


# ---------- Plot utils ----------
MARGINS = dict(l=140, r=60, t=60, b=70)


def _shared_xaxis_layout(fig: go.Figure, gene_info: Dict[str, Any]) -> go.Figure:
    fig.update_xaxes(
        range=[gene_info["start"], gene_info["end"]], tickformat="d", zeroline=False, fixedrange=True
    )
    return fig


def add_marker_line(fig: go.Figure, pos: int, color: str = "black") -> None:
    """Add a vertical line to a genomic figure at a given coordinate.
    Why: visual alignment across plots for the same locus.
    """
    fig.add_vline(
        x=pos,
        line_color=color,
        line_width=2,
        opacity=0.95,
        annotation_text=f"Pos {pos}",
        annotation_position="top",
    )


def create_pie(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title="No variants")
        return fig
    counts = df["consequence"].value_counts()
    palette = px.colors.qualitative.T10
    fig = px.pie(
        names=counts.index,
        values=counts.values,
        color=counts.index,
        color_discrete_map={c: palette[i % len(palette)] for i, c in enumerate(counts.index)},
    )
    fig.update_traces(textinfo="percent+label", textposition="outside", pull=[0.03] * len(counts))
    fig.update_layout(showlegend=False, margin=dict(l=10, r=10, t=10, b=10), height=420)
    return fig


def create_bar_plot(
    df: pd.DataFrame,
    gene_info: Dict[str, Any],
    bin_size: int = 100,
    title: str = "Average AF by consequence and position bins (bar plot)",
) -> go.Figure:
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title="No variant data available", margin=MARGINS)
        return _shared_xaxis_layout(fig, gene_info)

    bins = np.arange(gene_info["start"], gene_info["end"] + bin_size, bin_size)
    df = df.copy()
    df["pos_bin"] = pd.cut(df["pos"], bins=bins, right=False)
    grouped = (
        df.groupby(["consequence", "pos_bin"], observed=False)
        .agg(mean_af=("af", "mean"))
        .reset_index()
    )
    grouped["bin_left"] = grouped["pos_bin"].apply(lambda x: int(x.left) if pd.notna(x) else None)

    palette = px.colors.qualitative.T10
    color_map = {c: palette[i % len(palette)] for i, c in enumerate(grouped["consequence"].unique())}

    fig = go.Figure()
    for cons in grouped["consequence"].unique():
        g = grouped[grouped["consequence"] == cons].sort_values("bin_left")
        fig.add_trace(
            go.Bar(
                x=g["bin_left"],
                y=g["mean_af"],
                width=bin_size * 0.9,
                name=cons,
                marker_color=color_map[cons],
                hovertemplate="Bin start: %{x}<br>Mean AF: %{y:.6f}<extra>" + cons + "</extra>",
            )
        )

    fig.update_layout(
        barmode="stack",
        title=title,
        xaxis_title="Genomic position",
        yaxis_title="Mean Allele Frequency (AF)",
        height=480,
        margin=MARGINS,
        legend=dict(orientation="v", x=1.02, y=0.9, font=dict(size=14)),
        font=dict(size=14),
    )
    return _shared_xaxis_layout(fig, gene_info)


def create_clinvar_bar_plot_like_gnomad(
    df: pd.DataFrame,
    gene_info: Dict[str, Any],
    bin_size: int = 100,
    title: str = "ClinVar variants (stacked by significance)",
    gnomad_positions: pd.Series | None = None,
) -> go.Figure:
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title="No ClinVar variants", margin=MARGINS)
        return _shared_xaxis_layout(fig, gene_info)

    df = df.copy()
    if gnomad_positions is not None and len(gnomad_positions) > 0:
        df["in_gnomad"] = df["pos"].isin(set(map(int, gnomad_positions.dropna().astype(int))))
    else:
        df["in_gnomad"] = False

    bins = np.arange(gene_info["start"], gene_info["end"] + bin_size, bin_size)
    df["pos_bin"] = pd.cut(df["pos"], bins=bins, right=False)

    sigs = [
        "Pathogenic / likely pathogenic",
        "Uncertain significance / conflicting",
        "Benign / likely benign",
        "Other",
    ]
    palette = px.colors.qualitative.T10
    color_map = {s: palette[i % len(palette)] for i, s in enumerate(sigs)}

    g_all = df.groupby(["sig_bucket", "pos_bin"], observed=False).size().reset_index(name="count")
    g_all["bin_left"] = g_all["pos_bin"].apply(lambda x: int(x.left) if pd.notna(x) else None)
    g_in = (
        df[df["in_gnomad"]]
        .groupby(["sig_bucket", "pos_bin"], observed=False)
        .size()
        .reset_index(name="count")
    )
    g_in["bin_left"] = g_in["pos_bin"].apply(lambda x: int(x.left) if pd.notna(x) else None)

    fig = go.Figure()
    # traces 0..3: all; 4..7: only in gnomAD
    for s in sigs:
        g = g_all[g_all["sig_bucket"] == s].sort_values("bin_left")
        fig.add_trace(
            go.Bar(
                x=g["bin_left"],
                y=g["count"],
                width=bin_size * 0.9,
                name=s,
                marker_color=color_map[s],
                hovertemplate="Bin start: %{x}<br>Count: %{y}<extra>" + s + "</extra>",
                visible=True,
            )
        )
    for s in sigs:
        g = g_in[g_in["sig_bucket"] == s].sort_values("bin_left")
        fig.add_trace(
            go.Bar(
                x=g["bin_left"],
                y=g["count"],
                width=bin_size * 0.9,
                name=s + " (in gnomAD)",
                marker_color=color_map[s],
                hovertemplate="Bin start: %{x}<br>Count: %{y}<extra>" + s + "</extra>",
                visible=False,
            )
        )

    n = len(sigs)
    vis_all = [True] * n + [False] * n
    vis_gnm = [False] * n + [True] * n

    def only_mask(idx: int, base_vis: list) -> list:
        v = base_vis.copy()
        for i in range(n):
            v[i] = (i == idx) and v[i]
            v[i + n] = (i == idx) and v[i + n]
        return v

    fig.update_layout(
        barmode="stack",
        title=title,
        xaxis_title="Genomic position",
        yaxis_title="Variant count",
        height=480,
        margin=MARGINS,
        font=dict(size=14),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0.0, font=dict(size=12)),
        updatemenus=[
            dict(
                type="buttons",
                x=0.0,
                y=1.20,
                xanchor="left",
                direction="right",
                showactive=True,
                buttons=[
                    dict(label="All ClinVar", method="update", args=[{"visible": vis_all}]),
                    dict(label="Only in gnomAD", method="update", args=[{"visible": vis_gnm}]),
                ],
            ),
            dict(
                type="dropdown",
                x=1.0,
                y=1.20,
                xanchor="right",
                direction="down",
                showactive=True,
                buttons=[
                    dict(label="Show: all significance", method="update", args=[{"visible": vis_all}]),
                    dict(label="Show: Pathogenic only", method="update", args=[{"visible": only_mask(0, vis_all)}]),
                    dict(label="Show: Uncertain only", method="update", args=[{"visible": only_mask(1, vis_all)}]),
                    dict(label="Show: Benign only", method="update", args=[{"visible": only_mask(2, vis_all)}]),
                    dict(label="Show: Other only", method="update", args=[{"visible": only_mask(3, vis_all)}]),
                ],
            ),
        ],
    )
    return _shared_xaxis_layout(fig, gene_info)


def create_gene_structure_plot(
    gene_info: Dict[str, Any],
    gene_color: str = "#8b0000",
    tx_color: str = "#1f77b4",
    exon_color: str = "#1f77b4",
    main_tx_color: str = "#d62728",
) -> go.Figure:
    region_start, region_end = gene_info["start"], gene_info["end"]
    transcripts = sorted(
        gene_info["transcripts"], key=lambda t: (not t.get("is_canonical", False), t["start"])
    )
    n = len(transcripts)
    tx_y = {tx["id"]: n - i for i, tx in enumerate(transcripts)}

    shapes: List[Dict[str, Any]] = []
    annotations: List[Dict[str, Any]] = []

    shapes.append(
        dict(
            type="rect",
            x0=region_start,
            x1=region_end,
            y0=0.15,
            y1=0.25,
            fillcolor=gene_color,
            line=dict(width=0),
        )
    )
    annotations.append(
        dict(
            x=region_start,
            y=0.20,
            xanchor="right",
            text="Gene region",
            showarrow=False,
            font=dict(size=14, color=gene_color),
        )
    )

    exon_h = 0.42
    label_x_right = region_end + max(100, int((region_end - region_start) * 0.06))

    for tx in transcripts:
        y = tx_y[tx["id"]]
        is_main = bool(tx.get("is_canonical"))
        color_line = main_tx_color if is_main else tx_color
        color_exon = main_tx_color if is_main else exon_color

        shapes.append(dict(type="line", x0=tx["start"], x1=tx["end"], y0=y, y1=y, line=dict(color=color_line, width=2)))
        for ex in tx["exons"]:
            shapes.append(
                dict(
                    type="rect",
                    x0=ex["start"],
                    x1=ex["end"],
                    y0=y - exon_h / 2,
                    y1=y + exon_h / 2,
                    fillcolor=color_exon,
                    line=dict(width=0),
                )
            )

        label = tx.get("display_name") or tx["id"]
        badges = []
        if tx.get("refseq_mrna"):
            badges.append("RefSeq: " + ",".join(tx["refseq_mrna"]))
        if tx.get("is_canonical"):
            badges.append("canonical")
        if tx.get("mane_candidate"):
            badges.append("MANE")
        txt = html.escape(f"{label}  [" + "; ".join(badges) + "]" if badges else label)
        annotations.append(
            dict(x=label_x_right, y=y, xanchor="left", text=txt, showarrow=False, font=dict(size=16), align="left"),
        )
        annotations.append(
            dict(
                x=tx["end"],
                y=y + 0.25,
                xanchor="left",
                text=html.escape(tx["id"]),
                showarrow=False,
                font=dict(size=11, color="#555"),
            )
        )

    fig = go.Figure()
    fig.update_layout(shapes=shapes, annotations=annotations)
    fig.update_yaxes(range=[0, n + 1], showticklabels=False, title_text="", fixedrange=True, visible=False)
    fig.update_layout(height=max(380, 46 * n + 100), margin=dict(l=140, r=260, t=40, b=30), font=dict(size=14))
    return _shared_xaxis_layout(fig, gene_info)


def prepare_left_summary_html(gene_info: Dict[str, Any]) -> str:
    transcripts = sorted(
        gene_info["transcripts"], key=lambda t: (not t.get("is_canonical", False), t["start"])
    )
    lines = [
        f"<b>Genome build</b> {html.escape(gene_info['assembly'])}<br>",
        f"<b>Ensembl gene ID</b> {html.escape(gene_info['ensembl_gene_id'])}<br>",
        f"<b>Region</b> {html.escape(gene_info['region'])}<br><br>",
        "<b>Transcripts</b><br>",
    ]
    for tx in transcripts:
        s = f"{tx['id']}  {tx['display_name']}  {tx['start']}-{tx['end']}"
        if tx.get("refseq_mrna"):
            s += "  RefSeq: " + ",".join(tx["refseq_mrna"]) 
        if tx.get("is_canonical"):
            s += "  [canonical]"
        if tx.get("mane_candidate"):
            s += "  [MANE]"
        lines.append(html.escape(s) + "<br>")
    return "".join(lines)


# ---------- HTML ----------
def make_html_page(
    gene_info: Dict[str, Any],
    left_html_summary: str,
    pie_fig: go.Figure,
    bar_fig: go.Figure,
    gene_struct_fig: go.Figure,
    clinvar_fig: go.Figure,
    out_filename: str,
) -> str:
    pie_json = pie_fig.to_json()
    bar_json = bar_fig.to_json()
    gene_struct_json = gene_struct_fig.to_json()
    clinvar_json = clinvar_fig.to_json()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    html_text = f"""<!doctype html>
<html lang=\"ru\">
<head>
<meta charset=\"utf-8\"/>
<meta http-equiv=\"Cache-Control\" content=\"no-cache, no-store, must-revalidate\"/>
<meta http-equiv=\"Pragma\" content=\"no-cache\"/>
<meta http-equiv=\"Expires\" content=\"0\"/>
<title>Gene {html.escape(gene_info['display_name'])} gnomAD/ClinVar view</title>
<script src=\"https://cdn.plot.ly/plotly-latest.min.js\"></script>
<style>
body {{ font-family: Arial, sans-serif; padding:16px; max-width:1200px; margin:auto; }}
.header {{ display:flex; justify-content:space-between; align-items:center; flex-wrap: wrap; gap: 10px; }}
.container_top {{ display:flex; gap:18px; align-items:flex-start; flex-wrap: wrap; }}
.left_col {{ width:420px; flex-shrink: 0; }}
.right_col {{ flex:1; min-width: 500px; }}
.summary_box {{ border:1px solid #e6e6e6; padding:10px; margin-bottom:10px; white-space: pre-wrap; font-family: monospace; font-size:14px; }}
.plot_box {{ margin-top:24px; }}
.footer {{ margin-top:8px; color:#666; font-size:0.9em; }}
h2 {{ margin-bottom:8px; font-size: 20px; }}
</style>
</head>
<body>
<div class=\"header\">
  <h2>Gene {html.escape(gene_info['display_name'])} summary</h2>
  <div>region {html.escape(gene_info['region'])} | assembly {html.escape(gene_info['assembly'])}</div>
</div>

<div class=\"container_top\">
  <div class=\"left_col\">
    <div class=\"summary_box\">{left_html_summary}</div>
  </div>
  <div class=\"right_col\">
    <div id=\"pie_chart\" style=\"height:420px;\"></div>
  </div>
</div>

<div class=\"plot_box\">
  <h2>Average AF by consequence and genomic position (bar plot)</h2>
  <div id=\"bar_plot\" style=\"width:100%;height:480px;\"></div>
</div>

<div class=\"plot_box\">
  <h2>ClinVar variants (stacked by significance)</h2>
  <div id=\"clinvar_plot\" style=\"width:100%;height:480px;\"></div>
</div>

<div class=\"plot_box\">
  <h2>Gene structure (transcripts, exons, introns)</h2>
  <div id=\"gene_structure\" style=\"width:100%;height:auto; min-height:360px;\"></div>
</div>

<div class=\"footer\">Generated {now}</div>

<script>
var pie_fig = {pie_json};
var bar_fig = {bar_json};
var gene_struct_fig = {gene_struct_json};
var clinvar_fig = {clinvar_json};

Plotly.newPlot('pie_chart', pie_fig.data, pie_fig.layout, {{responsive: true}});
Plotly.newPlot('bar_plot', bar_fig.data, bar_fig.layout, {{responsive: true}});
Plotly.newPlot('clinvar_plot', clinvar_fig.data, clinvar_fig.layout, {{responsive: true}});
Plotly.newPlot('gene_structure', gene_struct_fig.data, gene_struct_fig.layout, {{responsive: true}});
</script>
</body>
</html>
"""
    with open(out_filename, "w", encoding="utf-8") as f:
        f.write(html_text)
    return out_filename


# ---------- CLI ----------
def main() -> None:
    print("Введите символ гена, например LDLR")
    symbol = input("Gene symbol: ").strip()
    if not symbol:
        print("Символ гена не введён, выход")
        return

    bin_size_in = input("Bin size для агрегации AF по умолчанию 100 (Enter для 100): ").strip() or "100"
    dataset = input("gnomAD dataset по умолчанию gnomad_r4 (Enter): ").strip() or "gnomad_r4"
    referenceGenome = input("Reference genome GRCh38 по умолчанию (Enter): ").strip() or "GRCh38"

    # coordinate marker (optional)
    marker_pos: Optional[int]
    try:
        marker_pos_in = input(
            "Введите координату для отметки на графиках (целое число; Enter — без отметки): "
        ).strip()
        marker_pos = int(marker_pos_in) if marker_pos_in else None
    except ValueError:
        marker_pos = None

    try:
        bin_size = int(bin_size_in)
    except Exception:
        bin_size = 100

    print(f"Looking up gene {symbol} in Ensembl...")
    try:
        gj = lookup_gene(symbol)
    except Exception as e:
        print("Ошибка Ensembl:", e)
        return

    gene_info = build_gene_summary(gj)
    gene_info["transcripts"] = annotate_transcripts(gene_info["transcripts"])
    left_html_summary = prepare_left_summary_html(gene_info)

    print("Fetching gnomAD variants...")
    try:
        variants = fetch_gnomad_variants_with_retry(
            gene_info["chrom"],
            gene_info["start"],
            gene_info["end"],
            referenceGenome=referenceGenome,
            dataset=dataset,
        )
    except Exception as e:
        print("Ошибка gnomAD:", e)
        variants = []

    df_gnomad = variants_to_dataframe(variants)
    print(f"Variants fetched: {len(df_gnomad)}. Building figures...")

    print("Fetching ClinVar variants...")
    clinvar_variants = fetch_clinvar_variants(
        gene_info["chrom"], gene_info["start"], gene_info["end"], referenceGenome=referenceGenome
    )
    df_clinvar = (
        clinvar_variants_to_dataframe(clinvar_variants)
        if clinvar_variants
        else pd.DataFrame(
            columns=[
                "variantId",
                "chrom",
                "pos",
                "ref",
                "alt",
                "clinical_significance",
                "review_status",
                "effect_bucket",
                "sig_bucket",
            ]
        )
    )

    pie_fig = create_pie(df_gnomad)
    bar_fig = create_bar_plot(df_gnomad, gene_info, bin_size=bin_size)
    clinvar_fig = create_clinvar_bar_plot_like_gnomad(
        df_clinvar,
        gene_info,
        bin_size=bin_size,
        gnomad_positions=df_gnomad.get("pos") if not df_gnomad.empty else None,
    )
    gene_struct_fig = create_gene_structure_plot(gene_info)

    # add the marker line to genomic plots
    if marker_pos is not None and gene_info["start"] <= marker_pos <= gene_info["end"]:
        add_marker_line(bar_fig, marker_pos)
        add_marker_line(clinvar_fig, marker_pos)
        add_marker_line(gene_struct_fig, marker_pos)
    elif marker_pos is not None:
        print(
            f"Внимание: координата {marker_pos} вне диапазона гена ({gene_info['start']}..{gene_info['end']}). Отметка пропущена."
        )

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    outname = f"gene_{symbol}_gnomad_summary_1_{ts}.html"
    make_html_page(gene_info, left_html_summary, pie_fig, bar_fig, gene_struct_fig, clinvar_fig, outname)

    print(f"Сохранён интерактивный html файл с графиками: {outname}")
    print("Откройте его в браузере (без кэша).")


# if __name__ == "__main__":
#     main()