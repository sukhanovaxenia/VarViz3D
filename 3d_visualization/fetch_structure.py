# 3d_visualization/fetch_structure.py
import math
import requests
from typing import List, Dict
from flask import Flask, jsonify, request
from flask_cors import CORS

TIMEOUT = 20
UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb"
ALPHAFOLD_PDB = "https://alphafold.ebi.ac.uk/files/AF-{uid}-F1-model_v4.pdb"

# ---------------- helpers ----------------
def _minmax01(arr: List[float]) -> List[float]:
    """0..1 нормализация. Массив 1-based, arr[0] пустой."""
    if len(arr) <= 1:
        return arr[:]
    v = arr[1:]
    vmax = max(v) if v else 0.0
    if vmax <= 0:
        return [0.0] * len(arr)
    return [0.0] + [x / vmax for x in v]

def _moving_avg(arr: List[float], k: int) -> List[float]:
    """Обычное скользящее среднее (несмещённое), длина сохраняется."""
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

# --------------- core fetcher ---------------
class StructureFetcher:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": "VarViz3D/0.2"})

    def _get(self, url: str):
        r = self.s.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        return r

    def alphafold_pdb_url(self, uni_id: str) -> str:
        return ALPHAFOLD_PDB.format(uid=uni_id)

    # ---- sequence & features from UniProt ----
    def _uniprot_json(self, uni_id: str) -> Dict:
        return self._get(f"{UNIPROT_BASE}/{uni_id}.json").json()

    def get_sequence(self, uni_id: str) -> Dict:
        j = self._uniprot_json(uni_id)
        seq = j.get("sequence", {}).get("value") or ""
        return {"uniprot": uni_id, "length": len(seq), "sequence": seq}

    def get_domain_info(self, uni_id: str) -> Dict:
        """
        Возвращает домен-подобные фичи:
        [{start,end,type,description}], + длину белка
        """
        j = self._uniprot_json(uni_id)
        L = len(j.get("sequence", {}).get("value") or "")
        ACCEPT = {
            "Domain", "Region", "DNA binding", "Zinc finger", "Repeat",
            "Coiled coil", "Topological domain", "Transmembrane"
        }
        out: List[Dict] = []
        for f in j.get("features", []):
            if f.get("type") not in ACCEPT:
                continue
            loc = f.get("location", {})
            try:
                start = int(loc["start"]["value"])
                end = int(loc["end"]["value"])
            except Exception:
                continue
            desc = (f.get("description") or f.get("type") or "").strip()
            out.append({"start": start, "end": end, "type": f.get("type"), "description": desc})
        out.sort(key=lambda x: (x["start"], x["end"]))
        return {"uniprot": uni_id, "length": L, "domains": out}

    # ---- Natural variants (UniProt) → треки ----
    def get_uniprot_variants(self, uni_id: str) -> Dict:
        """
        Natural variant: собираем позиции и метки «патогенности» из описаний.
        """
        j = self._uniprot_json(uni_id)
        L = len(j.get("sequence", {}).get("value") or "")
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
            desc = (f.get("description") or "").strip()
            low = desc.lower()
            pathogenic_hint = any(k in low for k in ["pathogenic", "disease", "cancer"])
            items.append({"pos": pos, "description": desc, "pathogenic_hint": pathogenic_hint})
        return {"length": L, "items": items}

    def build_variant_tracks(self, uni_id: str, win: int = 15) -> Dict:
        """
        Три массива 1-based длины L:
          raw.any  – все варианты
          raw.path – только с признаком «патогенные»
          raw.pop  – заглушка (0..0), сюда позже можно подать gnomAD частоты
        + smooth.* (скользящее среднее) и нормализация 0..1.
        """
        data = self.get_uniprot_variants(uni_id)
        L = data["length"]
        any_count   = [0.0] * (L + 1)
        patho_count = [0.0] * (L + 1)
        pop_freq    = [0.0] * (L + 1)  # TODO: подать реальные частоты

        for v in data["items"]:
            p = v["pos"]
            any_count[p] += 1.0
            if v["pathogenic_hint"]:
                patho_count[p] += 1.0

        any_sm  = _moving_avg(any_count, win)
        path_sm = _moving_avg(patho_count, win)
        pop_sm  = _moving_avg(pop_freq, win)

        return {
            "uniprot": uni_id,
            "length": L,
            "window": win,
            "raw": {
                "any":  _minmax01(any_count),
                "path": _minmax01(patho_count),
                "pop":  _minmax01(pop_freq),
            },
            "smooth": {
                "any":  _minmax01(any_sm),
                "path": _minmax01(path_sm),
                "pop":  _minmax01(pop_sm),
            }
        }

# ---------------- Flask API ----------------
app = Flask(__name__)
CORS(app)
F = StructureFetcher()

@app.get("/")
def root():
    return "VarViz3D API: /api/sequence/<id>, /api/domains/<id>, /api/tracks/<id>?win=15"

@app.get("/api/sequence/<uniprot_id>")
def api_sequence(uniprot_id: str):
    try:
        return jsonify(F.get_sequence(uniprot_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.get("/api/domains/<uniprot_id>")
def api_domains(uniprot_id: str):
    try:
        return jsonify(F.get_domain_info(uniprot_id))
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
