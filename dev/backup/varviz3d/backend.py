#!/usr/bin/env python3
"""
Unified backend serving both 3D viewer and API endpoints
Run: python backend.py
"""

from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS
import requests
import re
from typing import List, Dict, Any

app = Flask(__name__)
CORS(app, origins="*")

# Your existing backend_3d.py functions here (simplified for space)
TIMEOUT = 25
HEADERS = {"User-Agent": "VarViz3D/0.4"}
UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb"
PROTEINS_VAR = "https://www.ebi.ac.uk/proteins/api/variation?size=-1&accession={uid}"

# Embedded viewer HTML
VIEWER_HTML = '''<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <title>Protein 3D Structure Viewer</title>
  <script src="https://unpkg.com/ngl@latest/dist/ngl.js"></script>
  <style>
    body{ font-family: Arial, sans-serif; margin:0; padding:0; }
    #viewport{ width: 100%; height: 600px; border:0; }
  </style>
</head>
<body>
<div id="viewport"></div>
<script>
  const stage = new NGL.Stage("viewport", { backgroundColor: "white" });
  
  // Get UniProt ID from URL params
  const params = new URLSearchParams(window.location.search);
  const uniprot = params.get('uniprot') || 'P38398';
  
  // Load structure
  stage.loadFile(`https://alphafold.ebi.ac.uk/files/AF-${uniprot}-F1-model_v4.pdb`)
    .then(comp => {
      comp.addRepresentation("cartoon", { color: "sstruc" });
      comp.autoView();
    })
    .catch(err => {
      console.error("Failed to load structure:", err);
      document.getElementById("viewport").innerHTML = 
        '<div style="padding:20px;color:red;">Failed to load structure for ' + uniprot + '</div>';
    });
</script>
</body>
</html>'''

class StructureFetcher:
    """Minimal implementation for API endpoints"""
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update(HEADERS)
    
    def get_domain_info(self, uni_id: str) -> Dict[str, Any]:
        """Return mock domain info"""
        return {
            "uniprot": uni_id,
            "length": 1863,  # BRCA1 length
            "domains": [
                {"start": 1, "end": 103, "description": "RING domain", "type": "Domain"},
                {"start": 170, "end": 190, "description": "Nuclear localization", "type": "Region"},
                {"start": 1650, "end": 1863, "description": "BRCT domain", "type": "Domain"}
            ]
        }
    
    def build_variant_tracks(self, uni_id: str, win: int = 15) -> Dict[str, Any]:
        """Return mock variant tracks"""
        import random
        L = 1863
        classes = ["pathogenic", "benign", "uncertain", "predicted"]
        
        # Generate mock data
        mock_data = {"any": [0.0] + [random.random() for _ in range(L)]}
        for c in classes:
            mock_data[c] = [0.0] + [random.random() * 0.5 for _ in range(L)]
        
        return {
            "uniprot": uni_id,
            "length": L,
            "window": win,
            "classes": classes,
            "smooth": mock_data,
            "raw": mock_data,
            "bins": [],
            "source": "mock_data",
            "total_variants": 100
        }

F = StructureFetcher()

# Routes
@app.route('/')
def index():
    return "Backend running on port 5001"

@app.route('/3d/viewer')
def viewer():
    return VIEWER_HTML

@app.route('/api/domains/<uniprot_id>')
def api_domains(uniprot_id: str):
    try:
        return jsonify(F.get_domain_info(uniprot_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/tracks/<uniprot_id>')
def api_tracks(uniprot_id: str):
    try:
        win = int(request.args.get("win", "15"))
        return jsonify(F.build_variant_tracks(uniprot_id, win=win))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/resolve/<symbol>')
def api_resolve(symbol: str):
    """Simple gene symbol to UniProt resolver"""
    mapping = {
        "BRCA1": "P38398",
        "BRCA2": "P51587", 
        "TP53": "P04637",
        "EGFR": "P00533"
    }
    return jsonify({
        "query": symbol,
        "organism": 9606,
        "best": {"accession": mapping.get(symbol.upper(), "P38398")}
    })

if __name__ == "__main__":
    print("Starting backend on http://localhost:5001")
    print("3D Viewer: http://localhost:5001/3d/viewer")
    app.run(host="0.0.0.0", port=5001, debug=False)