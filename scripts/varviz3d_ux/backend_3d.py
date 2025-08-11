# backend_3d.py - Consolidated 3D backend
from __future__ import annotations
import os
import re
import requests
from typing import List, Dict, Any
from flask import Flask, jsonify, request, send_from_directory, render_template_string
from flask_cors import CORS

# Import your resolver if available
try:
    from gene_to_uniprot import UniProtResolver
except:
    class UniProtResolver:
        def resolve(self, symbol: str, organism: int = 9606) -> Dict[str, Any]:
            return {"symbol": symbol, "organism": organism, "note": "stub"}

TIMEOUT = 25
HEADERS = {"User-Agent": "VarViz3D/0.4"}
UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb"
PROTEINS_VAR = "https://www.ebi.ac.uk/proteins/api/variation?size=-1&accession={uid}"
VIEWER_HTML = r"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <title>Protein 3D Structure Viewer</title>
  <script src="https://unpkg.com/ngl@latest/dist/ngl.js"></script>
  <style>
    :root{ --accent:#f6c44f; --accent2:#c9a93b; --btn:#f6f6f6; --btnb:#bbb; --btntext:#222; }
    body{ font-family: system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif; margin:16px; }
    #viewport{ 
        width: calc(100% - 32px); 
        max-width: 1200px;
        height: 600px; 
        border:1px solid #ccc; 
        margin: 0 auto;
    }
    .row{ margin:10px 0; display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
    .hint{ color:#666; font-size:12px; }
    .pill{ padding:8px 12px; border:1px solid var(--btnb); border-radius:10px; background:var(--btn); cursor:pointer; }
    .pill.active{ background:var(--accent); border-color:var(--accent2); }
    .ghost{ margin-left: 18px; }

    /* heatmap legend with extra air */
    #legendBar{
      width:960px; height:14px; border:1px solid #ccc;
      background: linear-gradient(90deg, #0000FF, #FFFFFF, #FF0000);
      margin-top:6px; margin-bottom:6px;
    }
    #legendScale{
      width:960px; display:flex; justify-content:space-between; font-size:12px;
      margin-bottom:14px;
    }

    #heatmapPanel{ display:none; }
    #domainPanel{ display:none; }
    #varTrack{ border:1px solid #ddd; }

    .popover{ position:absolute; top:170px; left:24px; background:#fff; border:1px solid #ddd;
              border-radius:10px; box-shadow:0 10px 40px rgba(0,0,0,.15); padding:16px 18px; }
    .pop-title{ font-weight:700; font-size:20px; margin-bottom:8px; }
    .legend-item{ display:flex; align-items:center; gap:10px; margin:6px 0; font-size:20px; }
    .colorbox{ width:18px; height:18px; border:1px solid #ccc; }
  </style>
</head>
<body>

<h1 style="margin-bottom:8px;">Protein 3D Structure Viewer</h1>

<div class="row">
  <strong>Gene / UniProt:</strong>
  <input id="uniprotID" value="BRCA1" style="width:200px;">
  <button id="loadBtn" class="pill">Load structure</button>
  <span class="hint">Examples: BRCA1, P38398, P04637…</span>
</div>

<div id="viewport"></div>

<div class="row">
  <strong>Mode:</strong>
  <button id="mSStruc"  class="pill active">Secondary structure</button>
  <button id="mRainbow" class="pill">Rainbow</button>
  <button id="mHeat"    class="pill">Variants heatmap</button>
  <button id="mDomains" class="pill">Domains track</button>

  <span class="ghost"></span><strong>Style:</strong>
  <button id="sCartoon" class="pill active">Cartoon</button>
  <button id="sStick"   class="pill">Stick</button>
  <button id="sSphere"  class="pill">Sphere</button>

  <span class="ghost"></span>
  <button id="btnSpin" class="pill">Spin</button>

  <span class="ghost"></span><strong>rsID:</strong>
  <input id="rsInput" placeholder="rs123456" style="width:120px;">
  <button id="rsBtn" class="pill">Highlight</button>

  <span class="ghost"></span>
  <span class="hint" id="srcHint"></span>
</div>

<!-- Heatmap controls + legend + 2D stacked track -->
<div id="heatmapPanel">
  <div class="row">
    <strong>Heatmap:</strong>
    <select id="trackSel">
      <option value="any">All variants (density)</option>
      <option value="pathogenic">Pathogenic</option>
      <option value="benign">Benign</option>
      <option value="uncertain">Uncertain</option>
      <option value="predicted">Predicted</option>
    </select>
    <strong>Window:</strong>
    <input id="winSize" type="number" min="1" max="201" step="2" value="15" style="width:70px;">
    <button id="applyTrack" class="pill">Apply heatmap</button>
  </div>

  <div id="legendBar"></div>
  <div id="legendScale">
    <span>Low <span id="legendMin">0</span></span>
    <span>Medium</span>
    <span>High <span id="legendMax">1</span></span>
  </div>

  <canvas id="varTrack" width="960" height="120" style="margin-top:8px;"></canvas>
</div>

<!-- 2D domain track -->
<div id="domainPanel" class="row" style="flex-direction:column; align-items:flex-start;">
  <canvas id="domainTrack" width="960" height="140"></canvas>
  <span class="hint">Hover a domain to preview; click a bar to lock/unlock and zoom that region.</span>
</div>

<!-- Secondary-structure legend -->
<div id="ssPopover" class="popover" style="display:none;">
  <div class="pop-title">Secondary structure</div>
  <div class="legend-item"><span class="colorbox" style="background:magenta;"></span> α-helix</div>
  <div class="legend-item"><span class="colorbox" style="background:gold;"></span> β-sheet</div>
  <div class="legend-item"><span class="colorbox" style="background:#ddd;"></span> Coil/loop</div>
</div>

<script>
  // ---------- NGL setup ----------
  const stage = new NGL.Stage("viewport", { backgroundColor: "white" });
  window.addEventListener("resize", () => stage.handleResize(), false);

  const API_BASE =
    (location.hostname === "localhost" || location.hostname === "127.0.0.1")
      ? "http://localhost:5001"
      : `http://${location.hostname}:5001`;

  let comp = null;
  let mode = "sstruc";   // sstruc | rainbow | heat | domains
  let style = "cartoon"; // cartoon | stick | sphere
  let currentSchemeId = null;
  let lastTracks = null, lastDomains = null;
  let lockedDomain = null;

  // rsID highlight
  let highlightPos = null;
  let highlightRep = null;

  const Registry = NGL.ColormakerRegistry || NGL.ColorMakerRegistry;

  const CLASS_COLORS = {
    pathogenic: "#d73027",
    benign:     "#1a9850",
    uncertain:  "#fee08b",
    predicted:  "#91bfdb"
  };

  // ---------- helpers ----------
  function setActive(el, on){ el.classList.toggle("active", !!on); }
  function show(el, on){ el.style.display = on ? "block" : "none"; }
  function clearReps(){ if (comp) comp.removeAllRepresentations(); }

  function addStyleRep(color){
    const common = { color };
    if (style === "cartoon"){
      comp.addRepresentation("cartoon", { ...common, aspectRatio: 5, arrowSize: 1.2, scale: 0.7 });
      comp.addRepresentation("backbone", { opacity: 0.25 });
    } else if (style === "stick"){
      comp.addRepresentation("licorice", { ...common, multipleBond: true });
    } else {
      comp.addRepresentation("spacefill", { ...common, scale: 0.4 });
    }
  }

  function applyBaseColoring(){
    clearReps();
    if (mode === "rainbow") addStyleRep("residueindex");
    else addStyleRep("sstruc");
    applyHighlight3D(); // keep rs highlight
  }

  function applyDomainBase(){
    if (!comp) return;
    clearReps();
    const base = "#cfcfcf";
    if (style === "cartoon"){
      comp.addRepresentation("cartoon",  { color: base, opacity: 0.30, aspectRatio:5, arrowSize:1.2, scale:0.7 });
      comp.addRepresentation("backbone", { color: base, opacity: 0.40 });
    } else if (style === "stick"){
      comp.addRepresentation("licorice", { color: base, opacity: 0.35, multipleBond: true });
    } else {
      comp.addRepresentation("spacefill", { color: base, opacity: 0.30, scale: 0.4 });
    }
    applyHighlight3D();
  }

  function makeBWR(values01){
    return Registry.addScheme(function(){
      this.atomColor = function(atom){
        const v = values01[atom.resno] ?? 0.0;
        if (v <= 0.5){
          const t = v / 0.5;
          const r = Math.round(255 * t), g = Math.round(255 * t), b = 255;
          return (r<<16)|(g<<8)|b;
        } else {
          const t = (v - 0.5) / 0.5;
          const r = 255, g = Math.round(255*(1-t)), b = Math.round(255*(1-t));
          return (r<<16)|(g<<8)|b;
        }
      };
    });
  }

  // ---------- backend I/O ----------
  async function fetchTracks(uid, win){
    const r = await fetch(`${API_BASE}/api/tracks/${uid}?win=${win}`);
    if (!r.ok) throw new Error(`tracks ${r.status}`);
    lastTracks = await r.json();
    document.getElementById("srcHint").textContent =
      lastTracks?.source === "proteins_variation"
        ? `Variants: Proteins API (n=${lastTracks.total_variants})`
        : `Variants: UniProt fallback (n=${lastTracks?.total_variants ?? "?"})`;
    return lastTracks;
  }
  async function fetchDomains(uid){
    const r = await fetch(`${API_BASE}/api/domains/${uid}`);
    if (!r.ok) throw new Error(`domains ${r.status}`);
    lastDomains = await r.json();
    return lastDomains;
  }

  // resolve: Gene symbol → UniProt accession (if needed)
  function looksLikeUniProt(x){
    const s = (x||"").trim();
    return /^[OPQ][0-9][A-Z0-9]{3}[0-9](-\d+)?$/i.test(s) || /^[A-NR-Z][0-9]{5}(-\d+)?$/i.test(s);
  }
  async function resolveIfNeeded(input){
    if (looksLikeUniProt(input)) return input;
    const r = await fetch(`${API_BASE}/api/resolve/${encodeURIComponent(input)}?organism=9606`);
    if (!r.ok) throw new Error("resolve failed");
    const data = await r.json();
    const acc = data?.best?.accession;
    if (!acc) throw new Error("no accession for symbol");
    return acc;
  }

  // ---------- heatmap ----------
  async function applyHeatmap(which){
    const id  = await resolveIfNeeded(document.getElementById("uniprotID").value.trim());
    const win = parseInt(document.getElementById("winSize").value||"15",10);
    if (!lastTracks || lastTracks.uniprot !== id || lastTracks.window !== win){
      await fetchTracks(id, win);
      drawVariantTrack();
    }
    const arr = lastTracks?.smooth?.[which] || lastTracks?.smooth?.any;
    if (!arr) return;

    if (currentSchemeId && Registry.removeScheme) try { Registry.removeScheme(currentSchemeId); } catch {}
    currentSchemeId = makeBWR(arr);

    clearReps();
    addStyleRep(currentSchemeId);
    if (stage.viewer?.requestRender) stage.viewer.requestRender();

    const v = (arr || []).slice(1);
    const vmin = v.length ? Math.min(...v) : 0;
    const vmax = v.length ? Math.max(...v) : 1;
    document.getElementById("legendMin").textContent = vmin.toFixed(2);
    document.getElementById("legendMax").textContent = vmax.toFixed(2);

    applyHighlight3D();
  }

  function drawVariantTrack(){
    const canvas = document.getElementById("varTrack");
    if (!canvas || !lastTracks?.bins) return;
    const ctx = canvas.getContext("2d");
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0,0,W,H);

    let maxStack = 0;
    lastTracks.bins.forEach(b => {
      const s = Object.values(b.totals).reduce((a,v)=>a+v,0);
      if (s > maxStack) maxStack = s;
    });

    const pad = {l:36, r:6, t:10, b:22};
    const plotW = W - pad.l - pad.r, plotH = H - pad.t - pad.b;
    const n = lastTracks.bins.length;
    const barW = Math.max(2, Math.floor(plotW / n) - 2);

    canvas._barIndex = [];
    ctx.font = "12px system-ui";
    ctx.textBaseline = "middle";
    ctx.fillStyle = "#333";

    // Y axis
    ctx.strokeStyle = "#aaa";
    ctx.beginPath(); ctx.moveTo(pad.l-0.5, pad.t); ctx.lineTo(pad.l-0.5, pad.t + plotH); ctx.stroke();
    const ticks = 4;
    for (let i=0; i<=ticks; i++){
      const frac = i / ticks, y = pad.t + plotH * (1 - frac);
      const val = Math.round(maxStack * frac);
      ctx.beginPath(); ctx.moveTo(pad.l-4, y+0.5); ctx.lineTo(pad.l-0.5, y+0.5); ctx.stroke();
      const tw = ctx.measureText(String(val)).width;
      ctx.fillText(String(val), pad.l - 8 - tw, y);
    }

    // bars
    lastTracks.bins.forEach((b,i)=>{
      const x0 = pad.l + i * (plotW / n);
      let y = pad.t + plotH;
      ["predicted","uncertain","benign","pathogenic"].forEach(k=>{
        const val = b.totals[k] || 0; if (val<=0||maxStack<=0) return;
        const h = plotH * (val / maxStack);
        ctx.fillStyle = CLASS_COLORS[k];
        ctx.fillRect(x0, y-h, barW, h);
        y -= h;
      });
      canvas._barIndex.push({x:x0, y:pad.t, w:barW, h:plotH, start:b.start, end:b.end, totals:b.totals});
    });

    // rsID marker (black)
    if (highlightPos && lastTracks?.length){
      const L = lastTracks.length;
      const xPos = pad.l + Math.round((highlightPos-1)/L * plotW);
      ctx.save(); ctx.strokeStyle = "#000"; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(xPos+0.5, pad.t-2); ctx.lineTo(xPos+0.5, pad.t+plotH+2); ctx.stroke();
      ctx.restore();
    }

    // tooltip
    canvas.onmousemove = (ev)=>{
      const r = canvas.getBoundingClientRect();
      const mx = ev.clientX - r.left, my = ev.clientY - r.top;
      const hit = canvas._barIndex.find(b => mx>=b.x && mx<=b.x+b.w && my>=b.y && my<=b.y+b.h);
      canvas.title = hit ? (
        `${hit.start}-${hit.end}\n`+
        `pathogenic: ${hit.totals.pathogenic|0}\n`+
        `benign: ${hit.totals.benign|0}\n`+
        `uncertain: ${hit.totals.uncertain|0}\n`+
        `predicted: ${hit.totals.predicted|0}`
      ) : "";
    };
    canvas.onclick = (ev)=>{
      if (!comp) return;
      const r = canvas.getBoundingClientRect();
      const mx = ev.clientX - r.left, my = ev.clientY - r.top;
      const hit = canvas._barIndex.find(b => mx>=b.x && mx<=b.x+b.w && my>=b.y && my<=b.y+b.h);
      if (hit) comp.autoView(`${hit.start}-${hit.end}`);
    };

    // mini legend
    const yLeg = H - 10; let xLeg = pad.l;
    ["pathogenic","benign","uncertain","predicted"].forEach(k=>{
      ctx.fillStyle = CLASS_COLORS[k]; ctx.fillRect(xLeg, yLeg-8, 10, 10);
      ctx.fillStyle = "#333"; ctx.fillText(k, xLeg+14, yLeg);
      xLeg += ctx.measureText(k).width + 34;
    });
  }

  function drawDomainTrack(){
    const canvas = document.getElementById("domainTrack");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0,0,W,H);
    if (!lastDomains?.domains?.length) return;

    const L = lastDomains.length || Math.max(...lastDomains.domains.map(d=>d.end));
    const pad = {l:8, r:8, t:20, b:16};
    const plotW = W - pad.l - pad.r;
    const rowH = 18, gap = 6;

    const rows = [];
    canvas._domHits = [];

    function colorForIndex(i){
      const pal=["#e6194B","#3cb44b","#4363d8","#f58231","#911eb4","#46f0f0","#f032e6","#bcf60c",
                 "#fabebe","#008080","#e6beff","#9A6324","#fffac8","#800000","#aaffc3","#808000"];
      return pal[i % pal.length];
    }

    // domains
    lastDomains.domains.forEach((d,i)=>{
      const x1 = pad.l + Math.round((d.start-1)/L * plotW);
      const x2 = pad.l + Math.round((d.end)/L * plotW);
      const w  = Math.max(4, x2-x1);

      let row = 0; while (rows[row] && rows[row] > x1) row++; rows[row] = x2 + 6;
      const y = pad.t + row * (rowH + gap);
      const color = colorForIndex(i);

      ctx.fillStyle = color; ctx.globalAlpha = 0.9; ctx.fillRect(x1, y, w, rowH); ctx.globalAlpha = 1;
      ctx.strokeStyle = "#fff"; ctx.strokeRect(x1+.5, y+.5, w-1, rowH-1);

      canvas._domHits.push({x:x1, y:y, w:w, h:rowH, sele:`${d.start}-${d.end}`,
        label:`${d.type||"Domain"}: ${d.description||""} (${d.start}-${d.end})`, color});
    });

    // rsID marker (black)
    if (highlightPos && lastDomains?.domains?.length){
      const xPos = pad.l + Math.round((highlightPos-1)/L * plotW);
      ctx.save(); ctx.strokeStyle = "#000"; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(xPos+0.5, pad.t-2); ctx.lineTo(xPos+0.5, H - pad.b + 2); ctx.stroke();
      ctx.restore();
    }

    // hover/lock
    let hoverRep = null;
    canvas.onmousemove = (ev)=>{
      const r = canvas.getBoundingClientRect();
      const mx = ev.clientX - r.left, my = ev.clientY - r.top;
      const hit = canvas._domHits.find(b => mx>=b.x && mx<=b.x+b.w && my>=b.y && my<=b.y+b.h);
      canvas.title = hit ? hit.label : "";
      if (!comp || lockedDomain) return;
      if (hoverRep) { hoverRep.dispose(); hoverRep = null; }
      if (hit) hoverRep = comp.addRepresentation("cartoon", { sele: hit.sele, color: hit.color, opacity:0.95, scale:0.8 });
    };
    canvas.onmouseleave = ()=>{
      canvas.title = "";
      if (!lockedDomain && hoverRep){ hoverRep.dispose(); hoverRep = null; }
    };
    canvas.onclick = (event)=>{
      if (!comp) return;
      if (lockedDomain){ lockedDomain = null; if (hoverRep){ hoverRep.dispose(); hoverRep=null; } }
      else {
        const r = canvas.getBoundingClientRect();
        const mx = event.clientX - r.left, my = event.clientY - r.top;
        const hit = canvas._domHits.find(b => mx>=b.x && mx<=b.x+b.w && my>=b.y && my<=b.y+b.h);
        if (hit){ lockedDomain = { sele: hit.sele, color: hit.color }; comp.autoView(hit.sele); }
      }
    };
  }

  // 3D rsID highlight
  function applyHighlight3D(){
    if (!comp || !highlightPos) return;
    try { if (highlightRep) highlightRep.dispose(); } catch(e){}
    const sele = `${highlightPos}-${highlightPos}`;
    highlightRep = comp.addRepresentation("spacefill", { sele, color: "#00ff55", scale: 1.0, opacity: 1.0 });
    comp.addRepresentation("licorice", { sele, color: "#00ff55" });
  }

  async function highlightRsid(){
    const idResolved = await resolveIfNeeded(document.getElementById("uniprotID").value.trim());
    const rs = document.getElementById("rsInput").value.trim();
    if (!idResolved || !rs) return;

    const r = await fetch(`${API_BASE}/api/rspos/${idResolved}/${encodeURIComponent(rs)}`);
    if (!r.ok){ alert("Failed to resolve rsID"); return; }
    const data = await r.json();
    if (!data.positions || !data.positions.length){ alert("rsID not found for this protein"); return; }
    highlightPos = data.positions[0];

    applyHighlight3D();
    if (comp) comp.autoView(`${highlightPos}-${highlightPos}`);
    drawVariantTrack(); // redraw 2D with marker
    drawDomainTrack();
  }

  // ---------- UI wiring ----------
  const btnsMode = {
    sstruc:  document.getElementById("mSStruc"),
    rainbow: document.getElementById("mRainbow"),
    heat:    document.getElementById("mHeat"),
    domains: document.getElementById("mDomains")
  };
  const btnsStyle = {
    cartoon: document.getElementById("sCartoon"),
    stick:   document.getElementById("sStick"),
    sphere:  document.getElementById("sSphere")
  };

  function applyModeButtons(){
    Object.entries(btnsMode).forEach(([k,el]) => setActive(el, k===mode));
    show(document.getElementById("heatmapPanel"), mode === "heat");
    show(document.getElementById("domainPanel"), mode === "domains");
    show(document.getElementById("ssPopover"),  mode === "sstruc");
  }
  function applyStyleButtons(){
    Object.entries(btnsStyle).forEach(([k,el]) => setActive(el, k===style));
  }

  Object.entries(btnsMode).forEach(([k,el])=>{
    el.onclick = async () => {
      mode = k; applyModeButtons(); if (!comp) return;
      if (mode === "heat"){
        await applyHeatmap(document.getElementById("trackSel").value);
      } else if (mode === "domains") {
        const id = await resolveIfNeeded(document.getElementById("uniprotID").value.trim());
        if (!lastDomains || lastDomains.uniprot !== id) await fetchDomains(id);
        drawDomainTrack(); applyDomainBase();
      } else { applyBaseColoring(); }
    };
  });

  Object.entries(btnsStyle).forEach(([k,el])=>{
    el.onclick = async () => {
      style = k; applyStyleButtons(); if (!comp) return;
      if (mode === "heat")      await applyHeatmap(document.getElementById("trackSel").value);
      else if (mode === "domains") applyDomainBase();
      else applyBaseColoring();
    };
  });

  document.getElementById("btnSpin").onclick  = () => stage.setSpin(!stage.parameters.spin);
  document.getElementById("applyTrack").onclick = () => applyHeatmap(document.getElementById("trackSel").value);
  document.getElementById("rsBtn").onclick = () => highlightRsid().catch(console.error);

  async function loadStructure(){
    const raw = document.getElementById("uniprotID").value.trim();
    if (!raw) return alert("Enter Gene symbol or UniProt ID");
    const id = await resolveIfNeeded(raw);
    document.getElementById("uniprotID").value = id; // show resolved accession

    lockedDomain = null; lastTracks = null; lastDomains = null; highlightPos = null;
    try { if (highlightRep) highlightRep.dispose(); } catch(e){}

    stage.removeAllComponents();
    comp = await stage.loadFile(`https://alphafold.ebi.ac.uk/files/AF-${id}-F1-model_v4.pdb`);
    comp.autoView();

    if (mode === "heat")     await applyHeatmap(document.getElementById("trackSel").value);
    else if (mode === "domains") { await fetchDomains(id); drawDomainTrack(); applyDomainBase(); }
    else applyBaseColoring();
  }

  document.getElementById("loadBtn").onclick = () => loadStructure().catch(console.error);

  // init
  applyModeButtons(); applyStyleButtons();
  loadStructure().catch(console.error);
</script>
</body>
</html>"""

# Create app
app = Flask(__name__)
CORS(app)

# [Include all your helper functions from the original backend_3d.py here]
# _minmax_norm, _moving_avg, _stack_bins, classify_text_significance, normalize_clinsig_list

def _minmax_norm(arr: List[float]) -> List[float]:
    if len(arr) <= 1:
        return arr[:]
    v = arr[1:]
    vmax = max(v) if v else 0.0
    if vmax <= 0.0:
        return [0.0] * len(arr)
    return [0.0] + [x / vmax for x in v]

def _moving_avg(arr: List[float], k: int) -> List[float]:
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
    L = len(next(iter(per_class_counts.values()))) - 1
    bins: List[Dict[str, Any]] = []
    for start in range(1, L + 1, win):
        end = min(L, start + win - 1)
        totals = {k: 0.0 for k in per_class_counts.keys()}
        for pos in range(start, end + 1):
            for k, arr in per_class_counts.items():
                totals[k] += arr[pos]
        bins.append({"start": start, "end": end, "totals": totals})
    return bins

_cls_pat = {
    "pathogenic": re.compile(r"\blikely\s*pathogenic\b|\bpathogenic\b", re.I),
    "benign": re.compile(r"\blikely\s*benign\b|\bbenign\b", re.I),
    "uncertain": re.compile(r"\bVUS\b|\buncertain\b|\bconflicting\b", re.I),
    "predicted": re.compile(r"\b(predicted|computational|in\s*silico)\b", re.I),
}

def classify_text_significance(text: str) -> str:
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
    if re.search(r"\b(disease|cancer|tumou?r)\b", t, re.I):
        return "pathogenic"
    return "predicted"

def normalize_clinsig_list(vals: List[str] | None) -> str:
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

# [Include StructureFetcher class here]
class StructureFetcher:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update(HEADERS)

    def _get(self, url: str):
        return self.s.get(url, timeout=TIMEOUT)

    def _uniprot_json(self, uni_id: str) -> Dict[str, Any]:
        r = self._get(f"{UNIPROT_BASE}/{uni_id}.json")
        r.raise_for_status()
        return r.json()

    def get_domain_info(self, uni_id: str) -> Dict[str, Any]:
        j = self._uniprot_json(uni_id)
        features = j.get("features", []) or []
        ACCEPT = {
            "Domain", "Region", "DNA binding", "Zinc finger", 
            "Repeat", "Coiled coil", "Topological domain", "Transmembrane"
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
            except:
                continue
            desc = (f.get("description") or ftype).strip()
            out.append({"start": start, "end": end, "description": desc, "type": ftype})
        out.sort(key=lambda x: (x["start"], x["end"]))
        L = len(j.get("sequence", {}).get("value") or "")
        return {"uniprot": uni_id, "length": L, "domains": out}

    def _seq_len(self, j: Dict[str, Any]) -> int:
        return len(j.get("sequence", {}).get("value") or "")

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
            except:
                continue
            if pos < 1 or pos > L:
                continue
            desc = (f.get("description") or "")
            frm = f.get("wildType") or ""
            to = f.get("alternativeSequence") or ""
            items.append({
                "pos": pos, "from": frm, "to": to,
                "description": desc.strip(),
                "class_": classify_text_significance(desc),
                "source": "uniprot_feature"
            })
        return {"length": L, "items": items}

    def get_variation_with_clinsig(self, uni_id: str) -> Dict[str, Any]:
        r = self._get(PROTEINS_VAR.format(uid=uni_id))
        r.raise_for_status()
        arr = r.json() or []
        if isinstance(arr, dict) and "variants" in arr:
            arr = arr.get("variants") or []
        L = self._seq_len(self._uniprot_json(uni_id))
        items: List[Dict[str, Any]] = []
        for v in arr:
            pos = v.get("position")
            if not isinstance(pos, int) or pos < 1 or (L and pos > L):
                continue
            frm = v.get("wildType") or ""
            to = v.get("alternativeSequence") or ""
            cl = normalize_clinsig_list(v.get("clinicalSignificances"))
            items.append({
                "pos": pos, "from": frm, "to": to,
                "class_": cl,
                "raw_clinsig": v.get("clinicalSignificances") or [],
                "source": "proteins_variation"
            })
        return {"length": L, "items": items}

    def build_variant_tracks(self, uni_id: str, win: int = 15) -> Dict[str, Any]:
        try:
            data = self.get_variation_with_clinsig(uni_id)
            use_src = "proteins_variation"
        except:
            data = {"length": 0, "items": []}
            use_src = "error"
        
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
        
        out_smooth = {"any": _minmax_norm(_moving_avg(any_count, win))}
        for c in classes:
            out_smooth[c] = _minmax_norm(_moving_avg(per_class[c], win))
        
        out_raw = {"any": _minmax_norm(any_count)}
        for c in classes:
            out_raw[c] = _minmax_norm(per_class[c])
        
        bins = _stack_bins(per_class, win)
        
        return {
            "uniprot": uni_id, "length": L, "window": win,
            "classes": classes, "raw": out_raw, "smooth": out_smooth,
            "bins": bins, "source": use_src,
            "total_variants": len(data["items"])
        }
    
    def find_rsid_positions(self, uni_id: str, rsid: str):
        rsid = (rsid or "").strip().lower()
        if not rsid:
            return []
        pos_set = set()
        
        try:
            r = self._get(PROTEINS_VAR.format(uid=uni_id))
            r.raise_for_status()
            arr = r.json() or []
            if isinstance(arr, dict) and "variants" in arr:
                arr = arr.get("variants") or []
            for v in arr:
                xrefs = (v.get("xrefs") or [])
                for x in xrefs:
                    name = (x.get("name") or "").lower()
                    xid = (x.get("id") or "").lower()
                    if name in ("dbsnp", "dbsnp id", "dbsnp_id") and xid == rsid:
                        p = v.get("position")
                        if isinstance(p, int) and p > 0:
                            pos_set.add(p)
        except:
            pass
        
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
            except:
                pass
        
        return sorted(pos_set)

# Initialize fetcher and resolver
F = StructureFetcher()
R = UniProtResolver()

# API Routes
@app.get("/")
def root():
    return "VarViz3D API running on port 5001"

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
        return jsonify(F.build_variant_tracks(uniprot_id, win=win))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.get("/api/rspos/<uniprot_id>/<rsid>")
def api_rsid_pos(uniprot_id: str, rsid: str):
    try:
        positions = F.find_rsid_positions(uniprot_id, rsid)
        return jsonify({"uniprot": uniprot_id, "rsid": rsid, "positions": positions})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.get("/api/resolve/<symbol>")
def api_resolve(symbol: str):
    try:
        org = int(request.args.get("organism", "9606"))
        out = R.resolve(symbol, organism=org)
        return jsonify(out)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Serve the 3D viewer HTML
@app.route('/3d/viewer')
def viewer():
    # Read viewer.html from file if it exists
    viewer_path = os.path.join(os.path.dirname(__file__), 'viewer.html')
    if os.path.exists(viewer_path):
        with open(viewer_path, 'r') as f:
            return f.read()
    
    # Fallback: inline HTML (you should copy your viewer.html content here)
    return VIEWER_HTML 

if __name__ == "__main__":
    print("Starting 3D backend on http://localhost:5001")
    print("Viewer available at: http://localhost:5001/3d/viewer")
    app.run(host="0.0.0.0", port=5001, debug=False)