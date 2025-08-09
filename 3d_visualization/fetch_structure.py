# 3d_visualization/fetch_structure.py
import math
import requests
from typing import List, Dict
from flask import Flask, jsonify, request
from flask_cors import CORS

TIMEOUT = 20
UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb"
ALPHAFOLD_PDB = "https://alphafold.ebi.ac.uk/files/AF-{uid}-F1-model_v4.pdb"

# ---------- helpers ----------
def _minmax_norm(arr: List[float]) -> List[float]:
    """Return 0..1 normalization (arr is 1-based; index 0 kept)."""
    if len(arr) <= 1:
        return arr[:]
    v = arr[1:]  # ignore index 0 (we use 1-based residues)
    vmax = max(v) if v else 0.0
    if vmax <= 0:
        return [0.0] * len(arr)
    return [0.0] + [x / vmax for x in v]

def _moving_avg(arr: List[float], k: int) -> List[float]:
    """Simple sliding window average, keeps length, works on 1-based arrays."""
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

# ---------- core ----------
class StructureFetcher:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": "VarViz3D/0.1"})

    def _get(self, url: str):
        return self.s.get(url, timeout=TIMEOUT)

    # --- Domains from UniProt ---
    def get_domain_info(self, uni_id: str) -> List[Dict]:
        url = f"{UNIPROT_BASE}/{uni_id}.json"
        r = self._get(url)
        r.raise_for_status()
        features = r.json().get("features", [])

        ACCEPT = {
            "Domain", "Region", "DNA binding", "Zinc finger", "Repeat",
            "Coiled coil", "Topological domain", "Transmembrane"
        }
        out: List[Dict] = []
        for f in features:
            ftype = f.get("type")
            if ftype not in ACCEPT:
                continue
            loc = f.get("location", {})
            try:
                start = int(loc["start"]["value"])
                end = int(loc["end"]["value"])
            except Exception:
                continue
            desc = (f.get("description") or ftype).strip()
            out.append({"start": start, "end": end, "description": desc, "type": ftype})

        out.sort(key=lambda x: (x["start"], x["end"]))
        return out

    def alphafold_pdb_url(self, uni_id: str) -> str:
        return ALPHAFOLD_PDB.format(uid=uni_id)

    # --- Variants from UniProt (Natural variant) ---
    def _uniprot_json(self, uni_id: str) -> Dict:
        r = self._get(f"{UNIPROT_BASE}/{uni_id}.json")
        r.raise_for_status()
        return r.json()

    def _seq_len(self, j: Dict) -> int:
        return len(j.get("sequence", {}).get("value") or "")

    def get_uniprot_variants(self, uni_id: str) -> Dict:
        """
        Collect UniProt 'Natural variant' features.
        Returns:
          { "length": L, "items": [ {pos, from, to, description, pathogenic_hint}, ... ] }
        """
        j = self._uniprot_json(uni_id)
        L = self._seq_len(j)
        items: List[Dict] = []

        for f in j.get("features", []):
            if f.get("type") != "Natural variant":
                continue
            loc = f.get("location", {})
            try:
                pos = int(loc["start"]["value"])
            except Exception:
                continue
            if pos < 1 or pos > L:
                continue

            desc = (f.get("description") or "")
            low = desc.lower()
            pathogenic_hint = any(k in low for k in ["pathogenic", "disease", "cancer"])

            frm = f.get("wildType") or ""
            to = f.get("alternativeSequence") or ""

            items.append({
                "pos": pos,
                "from": frm,
                "to": to,
                "description": desc.strip(),
                "pathogenic_hint": pathogenic_hint
            })

        return {"length": L, "items": items}

    def build_variant_tracks(self, uni_id: str, win: int = 15) -> Dict:
        """
        Make per-residue arrays (1..L) for:
          - any_count   (all variants)
          - patho_count (pathogenic-hint subset)
          - pop_freq    (placeholder 0..1; future: gnomAD etc.)
        Also return normalized & smoothed versions (0..1).
        """
        data = self.get_uniprot_variants(uni_id)
        L = data["length"]
        any_count   = [0.0] * (L + 1)
        patho_count = [0.0] * (L + 1)
        pop_freq    = [0.0] * (L + 1)  # TODO: fill from population DB

        for v in data["items"]:
            pos = v["pos"]
            any_count[pos] += 1.0
            if v["pathogenic_hint"]:
                patho_count[pos] += 1.0

        any_sm  = _moving_avg(any_count, win)
        path_sm = _moving_avg(patho_count, win)
        pop_sm  = _moving_avg(pop_freq, win)

        return {
            "uniprot": uni_id,
            "length": L,
            "window": win,
            "raw": {
                "any":  _minmax_norm(any_count),
                "path": _minmax_norm(patho_count),
                "pop":  _minmax_norm(pop_freq),
            },
            "smooth": {
                "any":  _minmax_norm(any_sm),
                "path": _minmax_norm(path_sm),
                "pop":  _minmax_norm(pop_sm),
            }
        }

# ---- Flask API ----
app = Flask(__name__)
CORS(app)
F = StructureFetcher()

@app.get("/")
def root():
    return "VarViz3D API: /api/domains/<UniProtID>, /api/variants/<UniProtID>, /api/tracks/<UniProtID>?win=15"

@app.get("/api/domains/<uniprot_id>")
def api_domains(uniprot_id: str):
    try:
        return jsonify({"uniprot": uniprot_id, "domains": F.get_domain_info(uniprot_id)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Demo endpoint with a visible sine-wave frequency, useful to test coloring
@app.get("/api/variants/<uniprot_id>")
def api_variants(uniprot_id: str):
    try:
        length = 400
        freqs = [{"pos": pos, "freq": round((math.sin(pos/50) + 1) / 2, 3)} for pos in range(1, length+1)]
        return jsonify({"uniprot": uniprot_id, "frequencies": freqs})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.get("/api/tracks/<uniprot_id>")
def api_tracks(uniprot_id: str):
    try:
        win = int(request.args.get("win", "15"))
        return jsonify(F.build_variant_tracks(uniprot_id, win=win))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
