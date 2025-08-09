# 3d_visualization/fetch_structure.py
import requests
from typing import List, Dict, Optional
from flask import Flask, jsonify
from flask_cors import CORS

TIMEOUT = 20
UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb"
PDB_BASE = "https://data.rcsb.org/rest/v1/core/uniprot"
ALPHAFOLD_PDB = "https://alphafold.ebi.ac.uk/files/AF-{uid}-F1-model_v4.pdb"

class StructureFetcher:
    def __init__(self):
        self.s = requests.Session()

    def _get(self, url: str):
        return self.s.get(url, timeout=TIMEOUT)

    def get_domain_info(self, uni_id: str) -> List[Dict]:
        """
        Return UniProt features as domain-like ranges:
        [{"start":..,"end":..,"description":..,"type":..}, ...]
        """
        url = f"{UNIPROT_BASE}/{uni_id}.json"
        r = self._get(url); r.raise_for_status()
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

# ---- Flask API ----
app = Flask(__name__)
CORS(app)
F = StructureFetcher()

@app.get("/")
def root():
    return "VarViz3D API: /api/domains/<uniprot_id>"

@app.get("/api/domains/<uniprot_id>")
def api_domains(uniprot_id: str):
    try:
        return jsonify({"uniprot": uniprot_id, "domains": F.get_domain_info(uniprot_id)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Run alongside your static server
    app.run(host="0.0.0.0", port=5001)
