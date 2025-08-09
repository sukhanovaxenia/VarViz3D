# ----------------------------------------------------------------------
# VarViz3D backend (rewritten)
# - /api/domains/<UniProtID>         : UniProt domain-like features
# - /api/tracks/<UniProtID>?win=15   : per-class variant tracks + 2D bins
# - /api/debug/<UniProtID>           : quick peek of fetched variants
# - /api/compare/<UniProtID>         : UniProt vs Proteins API counts
#
# Variant source priority:
#   1) EMBL-EBI Proteins API /variation (has clinicalSignificances)
#   2) Fallback: UniProt "Natural variant" features + heuristic text parser
# ----------------------------------------------------------------------

from __future__ import annotations
import re
import requests
from typing import List, Dict, Any
from flask import Flask, jsonify, request
from flask_cors import CORS

TIMEOUT = 25
HEADERS = {"User-Agent": "VarViz3D/0.3"}

UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb"
PROTEINS_VAR = "https://www.ebi.ac.uk/proteins/api/variation?size=-1&accession={uid}"


# ---------- numeric helpers (arrays are 1-based; index 0 kept) ----------
def _minmax_norm(arr: List[float]) -> List[float]:
    """Normalize to 0..1; keep index 0 (we use 1-based residues)."""
    if len(arr) <= 1:
        return arr[:]
    v = arr[1:]
    vmax = max(v) if v else 0.0
    if vmax <= 0.0:
        return [0.0] * len(arr)
    return [0.0] + [x / vmax for x in v]


def _moving_avg(arr: List[float], k: int) -> List[float]:
    """Simple sliding-window average; preserves length; 1-based arrays OK."""
    if k <= 1:
        return arr[:]
    out = [0.0] * len(arr)
    s = 0.0
    q: List[float] = []
    for i, x in enumerate(arr):
        s += x
        q.append(x)
        if len(q) > k:
            s -= q.pop(0)
        out[i] = s / len(q)
    return out


def _stack_bins(per_class_counts: Dict[str, List[float]], win: int) -> List[Dict[str, Any]]:
    """
    Bin per-residue counts into windows for drawing a 2D stacked track.
    Returns: [{start, end, totals:{pathogenic, benign, uncertain, predicted}}, ...]
    """
    L = len(next(iter(per_class_counts.values()))) - 1  # arrays are 1-based
    bins: List[Dict[str, Any]] = []
    for start in range(1, L + 1, win):
        end = min(L, start + win - 1)
        totals = {k: 0.0 for k in per_class_counts.keys()}
        for pos in range(start, end + 1):
            for k, arr in per_class_counts.items():
                totals[k] += arr[pos]
        bins.append({"start": start, "end": end, "totals": totals})
    return bins


# ---------- significance classification ----------
_cls_pat = {
    "pathogenic": re.compile(r"\blikely\s*pathogenic\b|\bpathogenic\b", re.I),
    "benign": re.compile(r"\blikely\s*benign\b|\bbenign\b", re.I),
    "uncertain": re.compile(r"\bVUS\b|\buncertain\b|\bconflicting\b", re.I),
    "predicted": re.compile(r"\b(predicted|computational|in\s*silico)\b", re.I),
}


def classify_text_significance(text: str) -> str:
    """
    Heuristic mapper for UniProt feature description text.
    Returns one of: pathogenic | benign | uncertain | predicted
    """
    t = (text or "").strip()
    if not t:
        return "predicted"
    if _cls_pat["pathogenic"].search(t):
        return "pathogenic"
    if _cls_pat["benign"].search(t):
        return "benign"
    if _cls_pat["uncertain"].search(t):
        return "uncertain"
    if _cls_pat["predicted"].search(t):
        return "predicted"
    # weak signals
    if re.search(r"\b(disease|cancer|tumou?r)\b", t, re.I):
        return "pathogenic"
    return "predicted"


def normalize_clinsig_list(vals: List[str] | None) -> str:
    """
    Map clinicalSignificances array from Proteins API to our 4 classes.
    """
    if not vals:
        return "predicted"
    t = " ".join([v or "" for v in vals]).lower()
    if any(x in t for x in ["pathogenic", "likely_pathogenic"]):
        return "pathogenic"
    if any(x in t for x in ["benign", "likely_benign"]):
        return "benign"
    if any(x in t for x in ["uncertain", "vus", "conflicting"]):
        return "uncertain"
    return "predicted"


# ---------- core fetcher ----------
class StructureFetcher:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update(HEADERS)

    def _get(self, url: str):
        return self.s.get(url, timeout=TIMEOUT)

    # ---- UniProt JSON ----
    def _uniprot_json(self, uni_id: str) -> Dict[str, Any]:
        r = self._get(f"{UNIPROT_BASE}/{uni_id}.json")
        r.raise_for_status()
        return r.json()

    # ---- domains / regions from UniProt JSON ----
    def get_domain_info(self, uni_id: str) -> Dict[str, Any]:
        j = self._uniprot_json(uni_id)

        features = j.get("features", []) or []
        ACCEPT = {
            "Domain",
            "Region",
            "DNA binding",
            "Zinc finger",
            "Repeat",
            "Coiled coil",
            "Topological domain",
            "Transmembrane",
        }
        out: List[Dict[str, Any]] = []
        for f in features:
            ftype = f.get("type")
            if ftype not in ACCEPT:
                continue
            loc = f.get("location", {}) or {}
            try:
                start = int(loc["start"]["value"])
                end = int(loc["end"]["value"])
            except Exception:
                continue
            desc = (f.get("description") or ftype).strip()
            out.append({"start": start, "end": end, "description": desc, "type": ftype})
        out.sort(key=lambda x: (x["start"], x["end"]))

        L = len(j.get("sequence", {}).get("value") or "")
        return {"uniprot": uni_id, "length": L, "domains": out}

    def _seq_len(self, j: Dict[str, Any]) -> int:
        return len(j.get("sequence", {}).get("value") or "")

    # ---- UniProt "Natural variant" features -> simple variant list (fallback) ----
    def get_uniprot_variants(self, uni_id: str) -> Dict[str, Any]:
        j = self._uniprot_json(uni_id)
        L = self._seq_len(j)
        items: List[Dict[str, Any]] = []

        for f in j.get("features", []) or []:
            if f.get("type") != "Natural variant":
                continue
            loc = f.get("location", {}) or {}
            try:
                pos = int(loc["start"]["value"])
            except Exception:
                continue
            if pos < 1 or pos > L:
                continue
            desc = (f.get("description") or "")
            frm = f.get("wildType") or ""
            to = f.get("alternativeSequence") or ""
            items.append(
                {
                    "pos": pos,
                    "from": frm,
                    "to": to,
                    "description": desc.strip(),
                    "class_": classify_text_significance(desc),
                    "source": "uniprot_feature",
                }
            )

        return {"length": L, "items": items}

    # ---- Proteins API variation (preferred) ----
    def get_variation_with_clinsig(self, uni_id: str) -> Dict[str, Any]:
        """
        Fetch variations from EMBL-EBI Proteins API for the given UniProt accession.
        Expected fields include: position, wildType, alternativeSequence,
        clinicalSignificances (array of strings).
        """
        r = self._get(PROTEINS_VAR.format(uid=uni_id))
        r.raise_for_status()
        arr = r.json() or []
        # Some responses wrap items, but the public API typically returns a list
        if isinstance(arr, dict) and "variants" in arr:
            arr = arr.get("variants") or []

        # We need sequence length for bounds; take from UniProt JSON
        L = self._seq_len(self._uniprot_json(uni_id))

        items: List[Dict[str, Any]] = []
        for v in arr:
            pos = v.get("position")
            if not isinstance(pos, int) or pos < 1 or (L and pos > L):
                continue
            frm = v.get("wildType") or ""
            to = v.get("alternativeSequence") or ""
            cl = normalize_clinsig_list(v.get("clinicalSignificances"))
            items.append(
                {
                    "pos": pos,
                    "from": frm,
                    "to": to,
                    "class_": cl,
                    "raw_clinsig": v.get("clinicalSignificances") or [],
                    "source": "proteins_variation",
                }
            )

        return {"length": L, "items": items}

    # ---- build per-class tracks + 2D bins ----
    def build_variant_tracks(self, uni_id: str, win: int = 15) -> Dict[str, Any]:
        # try Proteins API first
        try:
            data = self.get_variation_with_clinsig(uni_id)
            use_src = "proteins_variation"
        except Exception:
            data = {"length": 0, "items": []}
            use_src = "error"

        # fallback if nothing fetched
        if not data.get("items"):
            data = self.get_uniprot_variants(uni_id)
            use_src = "uniprot_feature_fallback"

        L = data["length"]
        classes = ["pathogenic", "benign", "uncertain", "predicted"]
        per_class = {c: [0.0] * (L + 1) for c in classes}
        any_count = [0.0] * (L + 1)

        for v in data["items"]:
            pos = v["pos"]
            c = v.get("class_") or "predicted"
            if c not in per_class:
                c = "predicted"
            per_class[c][pos] += 1.0
            any_count[pos] += 1.0

        # smoothed & normalized for 3D coloring
        out_smooth = {"any": _minmax_norm(_moving_avg(any_count, win))}
        for c in classes:
            out_smooth[c] = _minmax_norm(_moving_avg(per_class[c], win))

        # raw, also normalized 0..1 for optional uses
        out_raw = {"any": _minmax_norm(any_count)}
        for c in classes:
            out_raw[c] = _minmax_norm(per_class[c])

        # 2D stacked bins (absolute counts; nicer for bar heights)
        bins = _stack_bins(per_class, win)

        return {
            "uniprot": uni_id,
            "length": L,
            "window": win,
            "classes": classes,
            "raw": out_raw,
            "smooth": out_smooth,
            "bins": bins,
            "source": use_src,
            "total_variants": len(data["items"]),
        }
    
    def find_rsid_positions(self, uni_id: str, rsid: str):
        """
        Вернёт список позиций аминокислоты (residue numbers) для данного rsID.
        Ищем в Proteins API variation по xrefs (dbSNP), иначе — в UniProt features
        по вхождению rsID в description.
        """
        rsid = (rsid or "").strip().lower()
        if not rsid:
            return []

        pos_set = set()

        # 1) Proteins API variation
        try:
            r = self._get(PROTEINS_VAR.format(uid=uni_id))
            r.raise_for_status()
            arr = r.json() or []
            if isinstance(arr, dict) and "variants" in arr:
                arr = arr.get("variants") or []
            for v in arr:
                xrefs = (v.get("xrefs") or [])  # [{name:"dbSNP", id:"rs123"}]
                for x in xrefs:
                    name = (x.get("name") or "").lower()
                    xid  = (x.get("id") or "").lower()
                    if name in ("dbsnp", "dbsnp id", "dbsnp_id") and xid == rsid:
                        p = v.get("position")
                        if isinstance(p, int) and p > 0:
                            pos_set.add(p)
        except Exception:
            pass

        # 2) fallback: UniProt features (Natural variant) — ищем rsID в description
        if not pos_set:
            try:
                j = self._uniprot_json(uni_id)
                for f in j.get("features", []) or []:
                    if f.get("type") != "Natural variant":
                        continue
                    desc = (f.get("description") or "").lower()
                    if rsid in desc:
                        loc = f.get("location", {}) or {}
                        pos = int(loc["start"]["value"])
                        if pos > 0:
                            pos_set.add(pos)
            except Exception:
                pass

        return sorted(pos_set)



# ---- Flask wiring ----
app = Flask(__name__)
CORS(app)
F = StructureFetcher()


@app.get("/")
def root():
    return "VarViz3D API: /api/domains/<UniProtID>, /api/tracks/<UniProtID>?win=15, /api/debug/<UniProtID>, /api/compare/<UniProtID>"


@app.get("/api/domains/<uniprot_id>")
def api_domains(uniprot_id: str):
    try:
        return jsonify(F.get_domain_info(uniprot_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/tracks/<uniprot_id>")
def api_tracks(uniprot_id: str):
    try:
        win = max(1, int(request.args.get("win", "15")))
        if win % 2 == 0:  # odd window sizes look a bit nicer, but not required
            win += 1
        return jsonify(F.build_variant_tracks(uniprot_id, win=win))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------- debug endpoints ----------
@app.get("/api/debug/<uniprot_id>")
def api_debug(uniprot_id: str):
    try:
        # try both sources
        p = F.get_variation_with_clinsig(uniprot_id)
    except Exception as e:
        p = {"length": 0, "items": [], "error": f"proteins_api: {e}"}
    u = F.get_uniprot_variants(uniprot_id)

    def _by_class(items):
        d: Dict[str, int] = {}
        for it in items:
            d[it.get("class_") or "predicted"] = d.get(it.get("class_") or "predicted", 0) + 1
        return d

    return jsonify(
        {
            "uniprot": uniprot_id,
            "proteins_api_total": len(p.get("items", [])),
            "proteins_api_by_class": _by_class(p.get("items", [])),
            "uniprot_features_total": len(u.get("items", [])),
            "uniprot_features_by_class": _by_class(u.get("items", [])),
            "sample_proteins_api": (p.get("items", [])[:10]),
            "sample_uniprot": (u.get("items", [])[:10]),
        }
    )


@app.get("/api/compare/<uniprot_id>")
def api_compare(uniprot_id: str):
    try:
        a = F.get_uniprot_variants(uniprot_id)
        b = F.get_variation_with_clinsig(uniprot_id)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    def count(items):
        c: Dict[str, int] = {}
        for it in items:
            k = it.get("class_") or "predicted"
            c[k] = c.get(k, 0) + 1
        return c

    return jsonify(
        {
            "uniprot": uniprot_id,
            "uniprot_features_total": len(a["items"]),
            "uniprot_features_by_class": count(a["items"]),
            "proteins_api_variation_total": len(b["items"]),
            "proteins_api_variation_by_class": count(b["items"]),
        }
    )

@app.get("/api/rspos/<uniprot_id>/<rsid>")
def api_rsid_pos(uniprot_id: str, rsid: str):
    try:
        positions = F.find_rsid_positions(uniprot_id, rsid)
        return jsonify({"uniprot": uniprot_id, "rsid": rsid, "positions": positions})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Run alongside your static server (use http.server or VS Code Live Server)
    app.run(host="0.0.0.0", port=5001, debug=False)
