#!/usr/bin/env python3
"""
variant_3d_viewer_v2.py
Build a polished, self-contained HTML viewer for 3D protein + variants using 3Dmol.js.

How to use (minimal):
    from variant_3d_viewer_v2 import build_html_view
    build_html_view(
        out_html="viewer.html",
        title="TP53 • PDB 6KZQ",
        pdb_source={"type":"pdb","id":"6kzq","chain":"A"},
        variants=[
            {"chain":"A","pdb_position":248,"label":"R248Q (pathogenic)","color":"#d62728","size":1.3,"group":"ClinVar:Pathogenic"},
            {"chain":"A","pdb_position":273,"label":"R273C (pathogenic)","color":"#d62728","size":1.3,"group":"ClinVar:Pathogenic"},
            {"chain":"A","pdb_position":175,"label":"R175H (VUS)","color":"#7f7f7f","size":1.0,"group":"ClinVar:VUS"}
        ],
        domains=[
            {"name":"p53_DNA-binding","start":100,"end":300,"color":"#6f42c1"}
        ],
        ss_colors={"helix":"#e76f51","sheet":"#2a9d8f","coil":"#3a86ff"},
        show_labels=True
    )
"""

from __future__ import annotations
from pathlib import Path
import json
from typing import List, Dict, Optional

def _html_template(payload_json:str) -> str:
    # 3Dmol CDN; works offline if already cached by browser. For fully offline, embed a local copy.
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Variant 3D Viewer</title>
<style>
  :root {{
    --header-h: 64px;
    --sidebar-w: 320px;
    --bg: #0b0e14;
    --panel: #121826;
    --text: #e6edf3;
    --muted: #a6b3c6;
    --chip: #1f2a44;
    --chip-muted: #24304c;
    --border: #22304a;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ height: 100%; margin: 0; background: var(--bg); color: var(--text); font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, Apple Color Emoji, Segoe UI Emoji; }}
  .app {{
    display: grid;
    grid-template-rows: var(--header-h) 1fr;
    height: 100vh;
  }}
  header {{
    display:flex; align-items:center; gap: 12px;
    padding: 12px 16px; border-bottom: 1px solid var(--border);
    background: linear-gradient(180deg, #0b0e14, #0d1320);
    position: sticky; top: 0; z-index: 5;
  }}
  header h1 {{ font-size: 18px; margin: 0; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  header .tags {{ display:flex; gap:8px; flex-wrap: wrap; }}
  .tag {{ background: var(--chip); border:1px solid var(--border); padding: 4px 8px; border-radius: 999px; font-size: 12px; color: var(--muted);}}

  .main {{
    display: grid;
    grid-template-columns: 1fr var(--sidebar-w);
    height: calc(100vh - var(--header-h));
    overflow: hidden;
  }}
  #viewer {{ width: 100%; height: 100%; position: relative; }}
  .sidebar {{
    border-left: 1px solid var(--border);
    background: var(--panel);
    padding: 14px;
    overflow-y: auto;
  }}
  .section {{ margin-bottom: 18px; }}
  .section h2 {{ font-size: 14px; margin: 0 0 8px; font-weight: 600; color: var(--muted);}}
  .legend-item {{ display:flex; align-items:center; gap:8px; margin:6px 0; font-size: 13px; }}
  .swatch {{ width: 14px; height: 14px; border-radius: 3px; border:1px solid #0006; }}
  .row {{ display:flex; gap:10px; align-items:center; flex-wrap: wrap; }}
  .checkbox {{ display:flex; gap:8px; align-items:center; font-size: 13px; }}
  .muted {{ color: var(--muted); font-size: 12px; }}
  button {{ background:#1a2336; border:1px solid var(--border); color: var(--text); border-radius: 8px; padding: 8px 10px; cursor: pointer; }}
  button:hover {{ background:#1d2640; }}
  .kbd {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; font-size: 12px; background: var(--chip-muted); padding:2px 6px; border-radius:6px; border:1px solid var(--border); color: var(--muted);}}
</style>
</head>
<body>
<div class="app">
  <header>
    <h1 id="title">Variant 3D Viewer</h1>
    <div class="tags" id="tags"></div>
  </header>
  <div class="main">
    <div id="viewer"></div>
    <aside class="sidebar">
      <div class="section">
        <h2>Secondary structure colors</h2>
        <div id="ss-legend"></div>
      </div>
      <div class="section">
        <h2>Domains</h2>
        <div id="domain-legend"></div>
      </div>
      <div class="section">
        <h2>Layers</h2>
        <div id="layer-toggles"></div>
      </div>
      <div class="section">
        <div class="muted">Tips: drag to rotate; scroll to zoom; shift+drag to pan. Reset: <span class="kbd">R</span></div>
      </div>
    </aside>
  </div>
</div>

<script src="https://3dmol.org/build/3Dmol.js"></script>
<script>
const payload = {payload_json};

function $(sel) {{ return document.querySelector(sel); }}
function el(tag, props={{}}, children=[]) {{
  const node = Object.assign(document.createElement(tag), props);
  for (const c of children) node.append(c);
  return node;
}}

function init() {{
  $('#title').textContent = payload.title || "Variant 3D Viewer";
  const tags = $('#tags');
  if (payload.tags) for (const t of payload.tags) tags.append(el('span', {{className:'tag', textContent:t}}));

  // Sidebar legends
  const ssLegend = $('#ss-legend');
  const ss = payload.ss_colors || {{helix:'#e76f51', sheet:'#2a9d8f', coil:'#3a86ff'}};
  const ssMap = [ ['Helix', ss.helix], ['Sheet', ss.sheet], ['Coil / Loop', ss.coil] ];
  for (const [label,color] of ssMap) {{
    const row = el('div', {{className:'legend-item'}}, [
      el('span', {{className:'swatch', style:`background:${{color}}`}}),
      el('span', {{textContent: label}})
    ]);
    ssLegend.append(row);
  }}

  const domLegend = $('#domain-legend');
  if (payload.domains && payload.domains.length) {{
    for (const d of payload.domains) {{
      const label = `${{d.name}}  [${{d.start}}–${{d.end}}]`;
      const row = el('div', {{className:'legend-item'}}, [
        el('span', {{className:'swatch', style:`background:${{d.color || '#6f42c1'}}`}}),
        el('span', {{textContent: label}})
      ]);
      domLegend.append(row);
    }}
  }} else {{
    domLegend.append(el('div', {{className:'muted', textContent:'No domain annotations provided'}}));
  }}

  // Viewer
  const viewer = $3Dmol.createViewer('viewer', {{ backgroundColor: '#0b0e14' }});
  let structureLoaded = false;

  function applyCartoonStyles() {{
    const ssc = payload.ss_colors || {{helix:'#e76f51', sheet:'#2a9d8f', coil:'#3a9dff'}};
    // 3Dmol can't directly color by SS with custom colors, so approximate by atom selections:
    viewer.setStyle({{}}, {{cartoon: {{color: 'lightgray', opacity: 0.8}}}});
    viewer.setStyle({{secondary:'H'}}, {{cartoon: {{color: ssc.helix, opacity: 0.9}}}});
    viewer.setStyle({{secondary:'S'}}, {{cartoon: {{color: ssc.sheet, opacity: 0.9}}}});
    viewer.setStyle({{secondary:'C'}}, {{cartoon: {{color: ssc.coil,  opacity: 0.9}}}});
  }}

  function addDomains() {{
    if (!payload.domains) return;
    const chain = payload.pdb_source.chain || undefined;
    for (const d of payload.domains) {{
      const color = d.color || '#6f42c1';
      viewer.addSurface($3Dmol.SurfaceType.VDW, {{
        opacity: 0.35, color: color
      }}, {{chain: chain, resi: [...Array(d.end-d.start+1).keys()].map(i=>i+d.start)}});
    }}
  }}

  function addVariants() {{
    const layers = {{}}; // group -> [shape ids]
    const defaultGroup = 'Variants';
    for (const v of (payload.variants || [])) {{
      const group = v.group || defaultGroup;
      const size  = v.size || 1.0;
      const color = v.color || '#e8c547';
      const sel = {{chain: v.chain, resi: v.pdb_position}};
      viewer.setStyle(sel, {{
        stick: {{color: color, radius: 0.25*size}},
        sphere: {{color: color, radius: 0.7*size}}
      }});
      if (payload.show_labels && v.label) {{
        viewer.addLabel(v.label, {{
          position: {{}}, // auto attach to selection centroid
          backgroundOpacity: 0.65,
          backgroundColor: 'black',
          fontColor: 'white',
          fontSize: 12,
          inFront: true,
          alignment: 'center',
          showBackground: true,
          fixed: false,
          useScreen: true,
          sel: sel
        }});
      }}
      (layers[group] ||= []).push(sel);
    }}
    return layers;
  }}

  function buildLayerToggles(layers) {{
    const box = $('#layer-toggles');
    box.innerHTML = '';
    for (const group in layers) {{
      const id = 'chk_' + group.replace(/\\W+/g,'_');
      const row = el('label', {{className:'checkbox'}}, [
        el('input', {{type:'checkbox', id:id, checked:true}}),
        el('span', {{textContent: group}})
      ]);
      row.querySelector('input').addEventListener('change', (e)=>{{
        const show = e.target.checked;
        // hide/show by resetting style for that selection set
        layers[group].forEach(sel=> {{
          viewer.setStyle(sel, show ? {{
            stick: {{color: '#ffffff'}}, // temp; will reapply with stored color below
          }} : {{}} }});
        }});
        // reapply proper style if showing (to keep original colors)
        if (show) addVariants();
        viewer.render();
      }});
      box.append(row);
    }}
    const resetBtn = el('button', {{textContent:'Reset view'}});
    resetBtn.addEventListener('click', ()=>{{ viewer.zoomTo(); viewer.render(); }});
    box.append(el('div', {{}}, [resetBtn]));
  }}

  // Load structure
  const src = payload.pdb_source || {};
  const done = ()=>{
    applyCartoonStyles();
    addDomains();
    const layers = addVariants();

    const variantSel = (payload.variants||[])
      .filter(v=>v.pdb_position && v.chain)
      .map(v=>({{chain:v.chain, resi:v.pdb_position}}));
    if (variantSel.length) { viewer.zoomTo(variantSel); } else { viewer.zoomTo(); }
    viewer.render();
    buildLayerToggles(layers||{{}});
  };

  function loadFromUrl(url){
    // Определяем формат по расширению
    const lower = (url||"").toLowerCase();
    const fmt = lower.endsWith(".cif") || lower.endsWith(".mmcif") ? "mmcif" : "pdb";
    fetch(url, {mode: "cors"})
      .then(r=>{
        if (!r.ok) throw new Error("HTTP "+r.status);
        return r.text();
      })
      .then(text=>{
        viewer.addModel(text, fmt);
        done();
      })
      .catch(err=>{
        console.error("Failed to load structure:", err);
        alert("Failed to load structure from " + url + " ("+err+")");
        viewer.render();
      });
  }

  if (src.type === 'pdb' && src.id) {
    // надёжнее чем download с внешних URL
    $3Dmol.download(`pdb:${src.id}`, viewer, done, {{ "doAssembly": false }});
  } else if (src.type === 'url' && src.url) {
    loadFromUrl(src.url);
  } else if (src.type === 'pdbtext' && src.text) {
    viewer.addModel(src.text, 'pdb'); done();
  } else {
    viewer.render();
  }

  // Keyboard shortcuts
  document.addEventListener('keydown', (e)=>{{
    if (e.key.toLowerCase() === 'r') {{ viewer.zoomTo(); viewer.render(); }}
  }});


document.addEventListener('DOMContentLoaded', init);
</script>
</body>
</html>""".replace("{payload_json}", payload_json)

def build_html_view(
    out_html: str | Path,
    title: str,
    pdb_source: Dict,
    variants: List[Dict],
    domains: Optional[List[Dict]] = None,
    ss_colors: Optional[Dict[str,str]] = None,
    tags: Optional[List[str]] = None,
    show_labels: bool = True
) -> Path:
    """
    Parameters
    ----------
    out_html : output file path.
    title : top title text.
    pdb_source : dict with one of:
        - {{'type':'pdb','id':'6kzq','chain':'A'}}
        - {{'type':'url','url':'https://...pdb'}}
        - {{'type':'pdbtext','text': '<PDB text>'}}
    variants : list of dicts with keys:
        chain, pdb_position, label (opt), color (opt '#rrggbb'), size (opt float), group (opt str)
    domains : list of dicts: name, start, end, color (opt)
    ss_colors : dict like {{'helix':'#e76f51','sheet':'#2a9d8f','coil':'#3a86ff'}}
    tags : list of strings to show as chips in the header
    show_labels : show text labels next to variants
    """
    payload = {
        "title": title,
        "pdb_source": pdb_source,
        "variants": variants or [],
        "domains": domains or [],
        "ss_colors": ss_colors or {{"helix":"#e76f51","sheet":"#2a9d8f","coil":"#3a86ff"}},
        "tags": tags or [],
        "show_labels": bool(show_labels),
    }
    html = _html_template(json.dumps(payload))
    out_path = Path(out_html).resolve()
    out_path.write_text(html, encoding="utf-8")
    return out_path

if __name__ == "__main__":
    import argparse, sys, json
    ap = argparse.ArgumentParser(description="Build a polished 3D viewer HTML for protein variants (3Dmol.js).")
    ap.add_argument("--out", required=True, help="Output HTML file")
    ap.add_argument("--title", required=True, help="Header title")
    ap.add_argument("--pdb-id", help="PDB id (e.g., 6kzq); if given, uses type=pdb")
    ap.add_argument("--pdb-url", help="Direct URL to PDB/mmCIF file; uses type=url")
    ap.add_argument("--pdbtext", help="PDB content as a text file path; uses type=pdbtext")
    ap.add_argument("--chain", default="A", help="Chain id (default A)")
    ap.add_argument("--variants-json", help="Path to JSON list of variants")
    ap.add_argument("--domains-json", help="Path to JSON list of domains")
    ap.add_argument("--tags", nargs="*", help="Header tags chip list")
    ap.add_argument("--labels", action="store_true", help="Show labels next to variants")
    args = ap.parse_args()

    if not (args.pdb_id or args.pdb_url or args.pdbtext):
        print("Provide --pdb-id or --pdb-url or --pdbtext", file=sys.stderr); sys.exit(2)

    if args.pdb_id:
        pdb_source = {{"type":"pdb","id":args.pdb_id.lower(),"chain":args.chain}}
    elif args.pdb_url:
        pdb_source = {{"type":"url","url":args.pdb_url,"chain":args.chain}}
    else:
        pdb_source = {{"type":"pdbtext","text": Path(args.pdbtext).read_text(), "chain": args.chain}}

    variants = json.loads(Path(args.variants_json).read_text()) if args.variants_json else []
    domains  = json.loads(Path(args.domains_json).read_text()) if args.domains_json else []

    out = build_html_view(
        out_html=args.out,
        title=args.title,
        pdb_source=pdb_source,
        variants=variants,
        domains=domains,
        ss_colors=None,
        tags=args.tags or [],
        show_labels=args.labels
    )
    print(out)

