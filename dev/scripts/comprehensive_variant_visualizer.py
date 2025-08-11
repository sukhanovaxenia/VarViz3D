#!/usr/bin/env python3
"""
comprehensive_variant_visualizer.py - Fixed version with domains and better visualization
"""

import argparse
import asyncio
import aiohttp
import json
import sys
from typing import List, Dict, Optional, Tuple
import myvariant
import numpy as np

class ComprehensiveVariantVisualizer:
    def __init__(self):
        self.mv = myvariant.MyVariantInfo()
        self.uniprot_api = "https://rest.uniprot.org/uniprotkb"
        self.sifts_api = "https://www.ebi.ac.uk/pdbe/api"
        
        # Common gene UniProt IDs
        self.common_genes = {
            'TP53': 'P04637',
            'BRCA1': 'P38398',
            'EGFR': 'P00533',
            'KRAS': 'P01116'
        }
    
    async def process_variants(self, gene: str, variant_input: str, input_type: str, 
                             window_size: int = 50, prefer_alphafold: bool = False, radius: float = 8.0):
        """Process target variant and find all nearby variants"""
        
        # 1. Parse input variant
        target_variants = self.parse_variant_input(variant_input, input_type)
        if not target_variants:
            raise ValueError("No valid variants found")
        
        target_variant = target_variants[0]  # Use first as primary target
        
        # 2. Get UniProt ID
        uniprot_id = await self.get_uniprot_id(gene)
        if not uniprot_id:
            raise ValueError(f"No UniProt ID found for {gene}")
        print(f"UniProt ID: {uniprot_id}")
        
        # 3. Get protein domains
        print("Fetching protein domains...")
        domains = await self.get_protein_domains(uniprot_id)
        print(f"Found {len(domains)} domains")
        
        # 4. Get all variants in the region
        print(f"Fetching variants within {window_size}bp window...")
        all_variants = await self.get_nearby_variants(target_variant, window_size)
        print(f"Found {len(all_variants)} variants in region")
        
        # 5. Annotate all variants
        print("Annotating all variants...")
        annotated = await self.annotate_variants(all_variants)
        
        # 6. Add gradient colors
        colored_variants = self.assign_gradient_colors(annotated)
        
        # 7. Get structure
        structure_data = await self.get_best_structure(uniprot_id, prefer_alphafold)
        print(f"Structure: {structure_data['source']} - {structure_data['id']}")
        
        # 8. Map variants to structure
        mapped_variants = await self.map_variants_sifts(uniprot_id, structure_data, colored_variants)
        
        # 9. Mark target variant clearly
        for v in mapped_variants:
            if (v['chr'] == target_variant['chr'] and 
                v['pos'] == target_variant['pos'] and
                v['ref'] == target_variant['ref'] and
                v['alt'] == target_variant['alt']):
                v['is_target'] = True
                v['color'] = '#FF00FF'  # Magenta for target
                v['size'] = 2.0  # Larger size
            else:
                v['is_target'] = False
        
        # 10. Create visualization
        self.create_comprehensive_visualization(gene, structure_data, mapped_variants, domains, radius)
    
    async def get_protein_domains(self, uniprot_id: str) -> List[Dict]:
        """Fetch protein domains from UniProt"""
        domains = []
        
        async with aiohttp.ClientSession() as session:
            url = f"{self.uniprot_api}/{uniprot_id}"
            params = {'format': 'json'}
            
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    # Extract domains (excluding interaction regions)
                    features = data.get('features', [])
                    for feature in features:
                        feature_type = feature.get('type', '')
                        
                        # Include only structural domains
                        if feature_type in ['Domain', 'Repeat', 'Zinc finger', 'Motif', 'Region']:
                            if 'interaction' not in feature.get('description', '').lower():
                                location = feature.get('location', {})
                                start = location.get('start', {}).get('value')
                                end = location.get('end', {}).get('value')
                                
                                if start and end:
                                    domains.append({
                                        'name': feature.get('description', feature_type),
                                        'type': feature_type,
                                        'start': start,
                                        'end': end,
                                        'color': self.get_domain_color(feature_type)
                                    })
        
        return sorted(domains, key=lambda x: x['start'])
    
    def get_domain_color(self, domain_type: str) -> str:
        """Assign colors to different domain types"""
        colors = {
            'Domain': '#4CAF50',
            'Repeat': '#2196F3',
            'Zinc finger': '#FF9800',
            'Motif': '#9C27B0',
            'Region': '#607D8B'
        }
        return colors.get(domain_type, '#757575')
    
    async def get_nearby_variants(self, target_variant: Dict, window_size: int) -> List[Dict]:
        """Query MyVariant for all variants in a genomic window"""
        
        chr_num = target_variant['chr']
        start = target_variant['pos'] - window_size
        end = target_variant['pos'] + window_size
        
        # Query MyVariant for range
        query = f'chr{chr_num}:{start}-{end}'
        
        # Search for variants in this region
        results = self.mv.query(
            query,
            fields='_id,clinvar,gnomad,cadd,dbnsfp',
            size=1000,  # Get up to 1000 variants
            species='human',
            assembly='hg38'
        )
        
        variants = []
        if 'hits' in results:
            for hit in results['hits']:
                # Parse the _id to get variant details
                variant_id = hit['_id']
                if ':g.' in variant_id:
                    # Format: chr17:g.7577120G>A
                    parts = variant_id.split(':g.')
                    chr_part = parts[0].replace('chr', '')
                    pos_change = parts[1]
                    
                    # Extract position and change
                    import re
                    match = re.match(r'(\d+)([A-Z]+)>([A-Z]+)', pos_change)
                    if match:
                        pos, ref, alt = match.groups()
                        variants.append({
                            'chr': chr_part,
                            'pos': int(pos),
                            'ref': ref,
                            'alt': alt,
                            '_myvariant_data': hit
                        })
        
        # Always add target variant
        target_found = False
        for v in variants:
            if (v['chr'] == target_variant['chr'] and 
                v['pos'] == target_variant['pos'] and
                v['ref'] == target_variant['ref'] and
                v['alt'] == target_variant['alt']):
                target_found = True
                break
        
        if not target_found:
            variants.append(target_variant)
        
        return variants
    
    def assign_gradient_colors(self, variants: List[Dict]) -> List[Dict]:
        """Assign gradient colors based on pathogenicity and frequency"""
        
        for variant in variants:
            # Base color on pathogenicity
            path = variant.get('pathogenicity', 'vus')
            freq = variant.get('frequency', 0)
            
            # Create gradient based on frequency (rare = more intense color)
            if freq == 0:
                intensity = 1.0
            elif freq < 0.0001:  # Ultra rare
                intensity = 0.9
            elif freq < 0.001:   # Very rare
                intensity = 0.7
            elif freq < 0.01:    # Rare
                intensity = 0.5
            else:                # Common
                intensity = 0.3
            
            # Apply gradient to base colors
            if path == 'pathogenic':
                # Red gradient
                variant['color'] = self.rgb_to_hex(
                    int(255 * intensity),
                    int(50 * (1 - intensity)),
                    int(50 * (1 - intensity))
                )
            elif path == 'benign':
                # Green gradient
                variant['color'] = self.rgb_to_hex(
                    int(50 * (1 - intensity)),
                    int(255 * intensity),
                    int(50 * (1 - intensity))
                )
            else:  # VUS
                # Yellow gradient
                variant['color'] = self.rgb_to_hex(
                    int(255 * intensity),
                    int(255 * intensity),
                    int(50 * (1 - intensity))
                )
            
            # Size based on CADD score
            cadd = variant.get('cadd', 0)
            if cadd > 30:
                variant['size'] = 1.5
            elif cadd > 20:
                variant['size'] = 1.2
            else:
                variant['size'] = 1.0
        
        return variants
    
    def rgb_to_hex(self, r: int, g: int, b: int) -> str:
        """Convert RGB to hex color"""
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def parse_variant_input(self, variant_input: str, input_type: str) -> List[Dict]:
        variants = []
        
        if input_type == 'variant':
            parts = variant_input.split(':')
            if len(parts) == 4:
                variants.append({
                    'chr': parts[0].replace('chr', ''),
                    'pos': int(parts[1]),
                    'ref': parts[2],
                    'alt': parts[3]
                })
        elif input_type == 'vcf':
            with open(variant_input, 'r') as f:
                for line in f:
                    if line.startswith('#') or not line.strip():
                        continue
                    parts = line.strip().split('\t')
                    if len(parts) >= 5:
                        variants.append({
                            'chr': parts[0].replace('chr', ''),
                            'pos': int(parts[1]),
                            'ref': parts[3],
                            'alt': parts[4].split(',')[0]
                        })
        
        return variants
    
    async def get_uniprot_id(self, gene: str) -> Optional[str]:
        # Check common genes first
        if gene.upper() in self.common_genes:
            return self.common_genes[gene.upper()]
        
        async with aiohttp.ClientSession() as session:
            params = {
                'query': f'gene:{gene} AND organism_id:9606 AND reviewed:true',
                'format': 'json',
                'size': 1
            }
            async with session.get(f"{self.uniprot_api}/search", params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('results'):
                        return data['results'][0]['primaryAccession']
        return None
    
    async def annotate_variants(self, variants: List[Dict]) -> List[Dict]:
        """Annotate variants, using cached data when available"""
        annotated = []
        
        for variant in variants:
            # Use cached MyVariant data if available
            if '_myvariant_data' in variant:
                result = variant['_myvariant_data']
            else:
                # Query MyVariant for this specific variant
                hgvs = f"chr{variant['chr']}:g.{variant['pos']}{variant['ref']}>{variant['alt']}"
                result = self.mv.getvariant(
                    hgvs,
                    fields='clinvar,gnomad,cadd,dbnsfp',
                    assembly='hg38'
                )
            
            # Extract annotations
            annotated_variant = variant.copy()
            
            # Pathogenicity
            clin_sig = result.get('clinvar', {}).get('clinical_significance', '') if result else ''
            if 'pathogenic' in str(clin_sig).lower():
                annotated_variant['pathogenicity'] = 'pathogenic'
            elif 'benign' in str(clin_sig).lower():
                annotated_variant['pathogenicity'] = 'benign'
            else:
                annotated_variant['pathogenicity'] = 'vus'
            
            # Frequency
            gnomad = result.get('gnomad', {}) if result else {}
            annotated_variant['frequency'] = gnomad.get('af', {}).get('af', 0)
            
            # CADD score
            cadd = result.get('cadd', {}) if result else {}
            annotated_variant['cadd'] = cadd.get('phred', 0)
            
            # Protein position (simplified)
            annotated_variant['protein_position'] = (variant['pos'] % 1000) // 3
            
            annotated.append(annotated_variant)
        
        return annotated
    
    async def get_best_structure(self, uniprot_id: str, prefer_alphafold: bool = False) -> Dict:
        async with aiohttp.ClientSession() as session:
            pdb_structure = None
            alphafold_structure = {
                'source': 'AlphaFold',
                'id': uniprot_id,
                'url': f'https://alphafold.ebi.ac.uk/files/AF-{uniprot_id}-F1-model_v4.pdb',
                'mappings': []
            }
            
            # Get PDB if available
            url = f"{self.sifts_api}/mappings/uniprot/{uniprot_id}"
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for pdb_data in data.get(uniprot_id, {}).get('PDB', {}).values():
                        if pdb_data:
                            pdb_id = pdb_data[0]['pdb_id']
                            pdb_structure = {
                                'source': 'PDB',
                                'id': pdb_id,
                                'url': f'https://files.rcsb.org/download/{pdb_id}.pdb',
                                'mappings': pdb_data
                            }
                            break
            
            if prefer_alphafold:
                return alphafold_structure
            return pdb_structure or alphafold_structure
    
    async def map_variants_sifts(self, uniprot_id: str, structure_data: Dict, 
                                 variants: List[Dict]) -> List[Dict]:
        mapped = []
        
        if structure_data['source'] == 'PDB' and structure_data.get('mappings'):
            for variant in variants:
                for mapping in structure_data['mappings']:
                    if (mapping['uniprot_start'] <= variant['protein_position'] <= 
                        mapping['uniprot_end']):
                        pdb_pos = (variant['protein_position'] - mapping['uniprot_start'] + 
                                  mapping['pdb_start'])
                        variant['pdb_position'] = pdb_pos
                        variant['chain'] = mapping['chain_id']
                        mapped.append(variant)
                        break
        else:
            # Direct mapping for AlphaFold
            for variant in variants:
                variant['pdb_position'] = variant['protein_position']
                variant['chain'] = 'A'
                mapped.append(variant)
        
        return mapped
    
    def create_comprehensive_visualization(self, gene: str, structure_data: Dict, 
                                         variants: List[Dict], domains: List[Dict], radius: float):
        """Create HTML with comprehensive variant visualization"""
        
        variants_js = json.dumps(variants)
        domains_js = json.dumps(domains)
        structure_url = structure_data['url']
        
        # Generate gradient legend
        gradient_legend = self.generate_gradient_legend()
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{gene} Comprehensive Variant Viewer</title>
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="https://3dmol.org/build/3Dmol-min.js"></script>
    <style>
        body {{ 
            font-family: Arial, sans-serif; 
            margin: 0; 
            padding: 0;
            background-color: #f5f5f5;
        }}
        .header {{
            background: white;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            position: relative;
            z-index: 10;
        }}
        h1 {{ margin: 0 0 10px 0; }}
        .main-container {{
            padding: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }}
        #container {{ 
            display: flex; 
            gap: 20px;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        #viewer {{ 
            width: 800px; 
            height: 600px; 
            border: 1px solid #ccc;
            position: relative;
        }}
        #controls {{ 
            width: 400px; 
            max-height: 600px; 
            overflow-y: auto;
            padding: 0 10px;
        }}
        .control-section {{
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 1px solid #eee;
        }}
        .variant-info {{ 
            margin: 5px 0; 
            padding: 8px; 
            border: 1px solid #ddd; 
            cursor: pointer; 
            font-size: 12px;
            border-radius: 4px;
            transition: all 0.2s;
        }}
        .variant-info:hover {{
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .target-variant {{ 
            border: 3px solid #FF00FF !important; 
            font-weight: bold;
            background: #FF00FF20 !important;
        }}
        button {{ 
            margin: 5px; 
            padding: 8px 12px; 
            cursor: pointer;
            background: #2196F3;
            color: white;
            border: none;
            border-radius: 4px;
            transition: background 0.2s;
        }}
        button:hover {{
            background: #1976D2;
        }}
        .legend {{ margin-top: 20px; }}
        .legend-item {{ 
            display: flex; 
            align-items: center; 
            margin: 5px 0; 
        }}
        .color-box {{ 
            width: 20px; 
            height: 20px; 
            margin-right: 10px; 
            border: 1px solid #000; 
        }}
        .gradient-legend {{ margin: 10px 0; }}
        .gradient-bar {{ 
            height: 20px; 
            width: 200px; 
            border: 1px solid #000; 
        }}
        .stats {{ 
            background: #f5f5f5; 
            padding: 10px; 
            margin: 10px 0;
            border-radius: 4px;
        }}
        .domain-list {{
            margin-top: 10px;
            font-size: 12px;
        }}
        .domain-item {{
            padding: 5px;
            margin: 3px 0;
            border-radius: 3px;
            cursor: pointer;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{gene} Comprehensive Variant Structure Viewer</h1>
        <p>Structure: {structure_data['source']} ({structure_data['id']}) | Total variants: <span id="variant-count">{len(variants)}</span> | Domains: {len(domains)}</p>
    </div>
    
    <div class="main-container">
        <div id="container">
            <div id="viewer"></div>
            <div id="controls">
                <div class="control-section">
                    <h3>Structure View</h3>
                    <button onclick="setStyle('cartoon')">Cartoon</button>
                    <button onclick="setStyle('stick')">Stick</button>
                    <button onclick="setStyle('sphere')">Sphere</button>
                    <button onclick="setStyle('surface')">Surface</button>
                    <br>
                    <button onclick="colorBySecondary()">Color by Secondary Structure</button>
                    <button onclick="colorByDomains()">Color by Domains</button>
                </div>
                
                <div class="control-section">
                    <h3>Variant Highlights</h3>
                    <button onclick="highlightTarget()" style="background: #FF00FF;">TARGET VARIANT</button>
                    <button onclick="highlightAll()">All Variants</button>
                    <button onclick="highlightPathogenic()">Pathogenic Only</button>
                    <button onclick="highlightRare()">Rare (AF<0.1%)</button>
                    <button onclick="resetView()">Reset View</button>
                </div>
                
                <div class="control-section">
                    <h3>Protein Domains</h3>
                    <div class="domain-list" id="domain-list"></div>
                </div>
                
                <div class="stats">
                    <h4>Variant Statistics</h4>
                    <div id="stats-content"></div>
                </div>
                
                <div class="legend">
                    <h3>Legend</h3>
                    <h4>Pathogenicity</h4>
                    <div class="legend-item">
                        <div class="color-box" style="background-color: #FF00FF;"></div>
                        <span><strong>TARGET VARIANT</strong></span>
                    </div>
                    <div class="legend-item">
                        <div class="color-box" style="background-color: #FF0000;"></div>
                        <span>Pathogenic</span>
                    </div>
                    <div class="legend-item">
                        <div class="color-box" style="background-color: #FFFF00;"></div>
                        <span>VUS</span>
                    </div>
                    <div class="legend-item">
                        <div class="color-box" style="background-color: #00FF00;"></div>
                        <span>Benign</span>
                    </div>
                    
                    <h4>Frequency Gradient</h4>
                    {gradient_legend}
                    
                    <h4>Size = CADD Score</h4>
                    <p style="font-size: 12px;">Larger = Higher CADD</p>
                </div>
                
                <div class="control-section">
                    <h3>All Variants ({len(variants)})</h3>
                    <div id="variant-list"></div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let viewer;
        let variants = {variants_js};
        let domains = {domains_js};
        let structure_url = '{structure_url}';
        let radius = {radius};
        
        // Calculate statistics
        function calculateStats() {{
            let stats = {{
                total: variants.length,
                pathogenic: 0,
                benign: 0,
                vus: 0,
                rare: 0,
                common: 0,
                target: 0
            }};
            
            variants.forEach(v => {{
                if (v.is_target) stats.target++;
                if (v.pathogenicity === 'pathogenic') stats.pathogenic++;
                else if (v.pathogenicity === 'benign') stats.benign++;
                else stats.vus++;
                
                if (v.frequency < 0.001) stats.rare++;
                else stats.common++;
            }});
            
            return stats;
        }}
        
        // Initialize viewer
        $(document).ready(function() {{
            let element = $('#viewer');
            let config = {{ backgroundColor: 'white' }};
            viewer = $3Dmol.createViewer(element, config);
            
            // Load structure
            jQuery.ajax(structure_url, {{
                success: function(data) {{
                    viewer.addModel(data, "pdb");
                    colorBySecondary();  // Default to secondary structure coloring
                    highlightTarget();    // Show target by default
                    viewer.zoomTo();
                    viewer.render();
                }},
                error: function(hdr, status, err) {{
                    console.error("Failed to load structure:", err);
                    alert("Failed to load structure from " + structure_url);
                }}
            }});
            
            updateVariantList();
            updateStats();
            updateDomainList();
        }});
        
        function setStyle(style) {{
            viewer.setStyle({{}}, {{[style]: {{}}}});
            colorBySecondary();
            highlightAll();
            viewer.render();
        }}
        
        function colorBySecondary() {{
            // Color by secondary structure
            viewer.setStyle({{}}, {{
                cartoon: {{
                    color: 'secondary',
                    opacity: 0.9
                }}
            }});
            viewer.render();
        }}
        
        function colorByDomains() {{
            // Base gray color
            viewer.setStyle({{}}, {{cartoon: {{color: 'lightgray', opacity: 0.7}}}});
            
            // Color each domain
            domains.forEach(function(domain) {{
                for (let i = domain.start; i <= domain.end; i++) {{
                    viewer.setStyle(
                        {{resi: i}},
                        {{cartoon: {{color: domain.color, opacity: 0.9}}}}
                    );
                }}
            }});
            
            viewer.render();
        }}
        
        function highlightTarget() {{
            // First set base structure
            colorBySecondary();
            
            let target = variants.find(v => v.is_target);
            if (target && target.pdb_position) {{
                // Highlight target with large magenta sphere
                viewer.addStyle(
                    {{chain: target.chain, resi: target.pdb_position}},
                    {{
                        sphere: {{color: '#FF00FF', radius: 2.5}},
                        cartoon: {{color: '#FF00FF', thickness: 1.5}}
                    }}
                );
                
                // Show residues within radius
                viewer.addStyle(
                    {{
                        within: {{distance: radius, sel: {{chain: target.chain, resi: target.pdb_position}}}}
                    }},
                    {{
                        stick: {{color: 'orange', radius: 0.15, opacity: 0.7}}
                    }}
                );
                
                // Add prominent label
                viewer.addLabel(
                    "TARGET: " + target.ref + target.protein_position + target.alt,
                    {{
                        position: {{chain: target.chain, resi: target.pdb_position}},
                        backgroundColor: 'magenta',
                        fontColor: 'white',
                        fontSize: 16,
                        backgroundOpacity: 0.9
                    }}
                );
                
                viewer.center({{chain: target.chain, resi: target.pdb_position}});
                viewer.zoom(0.8);
            }}
            
            viewer.render();
        }}
        
        function highlightAll() {{
            // Keep secondary structure coloring
            colorBySecondary();
            
            // Add all variants as spheres
            variants.forEach(function(variant) {{
                if (variant.pdb_position && variant.chain) {{
                    let size = variant.size || 1.0;
                    if (variant.is_target) size = 2.5;
                    
                    viewer.addStyle(
                        {{chain: variant.chain, resi: variant.pdb_position}},
                        {{
                            sphere: {{color: variant.color, radius: 0.8 * size}}
                        }}
                    );
                    
                    // Add label for target
                    if (variant.is_target) {{
                        viewer.addLabel(
                            "TARGET",
                            {{
                                position: {{chain: variant.chain, resi: variant.pdb_position}},
                                backgroundColor: 'magenta',
                                fontColor: 'white',
                                fontSize: 14
                            }}
                        );
                    }}
                }}
            }});
            
            viewer.render();
        }}
        
        function highlightPathogenic() {{
            colorBySecondary();
            
            variants.forEach(function(variant) {{
                if (variant.pathogenicity === 'pathogenic' && variant.pdb_position) {{
                    viewer.addStyle(
                        {{chain: variant.chain, resi: variant.pdb_position}},
                        {{
                            sphere: {{color: variant.color, radius: 1.2}}
                        }}
                    );
                }}
            }});
            
            viewer.render();
        }}
        
        function highlightRare() {{
            colorBySecondary();
            
            variants.forEach(function(variant) {{
                if (variant.frequency < 0.001 && variant.pdb_position) {{
                    viewer.addStyle(
                        {{chain: variant.chain, resi: variant.pdb_position}},
                        {{
                            sphere: {{color: variant.color, radius: 1.2}}
                        }}
                    );
                }}
            }});
            
            viewer.render();
        }}
        
        function resetView() {{
            colorBySecondary();
            viewer.zoomTo();
            viewer.render();
        }}
        
        function updateVariantList() {{
            let list = $('#variant-list');
            list.empty();
            
            // Sort variants by position
            let sortedVariants = [...variants].sort((a, b) => a.protein_position - b.protein_position);
            
            sortedVariants.forEach(function(variant, index) {{
                let bgColor = variant.is_target ? '#FF00FF30' : variant.color + '30';
                let div = $('<div>')
                    .addClass('variant-info')
                    .addClass(variant.is_target ? 'target-variant' : '')
                    .css('background-color', bgColor)
                    .html(`
                        <strong>${{variant.ref}}${{variant.protein_position}}${{variant.alt}}</strong>
                        ${{variant.is_target ? ' <span style="color: #FF00FF;">★ TARGET</span>' : ''}}<br>
                        Path: ${{variant.pathogenicity}} | 
                        AF: ${{variant.frequency ? variant.frequency.toExponential(1) : '0'}} | 
                        CADD: ${{variant.cadd ? variant.cadd.toFixed(1) : 'N/A'}}
                    `)
                    .click(function() {{
                        viewer.center({{chain: variant.chain, resi: variant.pdb_position}});
                        viewer.zoom(0.8);
                        viewer.render();
                    }});
                list.append(div);
            }});
        }}
        
        function updateDomainList() {{
            let list = $('#domain-list');
            list.empty();
            
            domains.forEach(function(domain) {{
                let div = $('<div>')
                    .addClass('domain-item')
                    .css('background-color', domain.color + '30')
                    .css('border-left', '4px solid ' + domain.color)
                    .html(`
                        <strong>${{domain.name}}</strong><br>
                        Residues: ${{domain.start}}-${{domain.end}} | Type: ${{domain.type}}
                    `)
                    .click(function() {{
                        // Highlight this domain
                        viewer.setStyle({{}}, {{cartoon: {{color: 'lightgray', opacity: 0.5}}}});
                        for (let i = domain.start; i <= domain.end; i++) {{
                            viewer.setStyle(
                                {{resi: i}},
                                {{cartoon: {{color: domain.color, opacity: 1.0}}}}
                            );
                        }}
                        viewer.render();
                    }});
                list.append(div);
            }});
        }}
        
        function updateStats() {{
            let stats = calculateStats();
            $('#stats-content').html(`
                <p><strong>Target Variant: ${{stats.target}}</strong></p>
                <p>Pathogenic: ${{stats.pathogenic}} (${{(stats.pathogenic/stats.total*100).toFixed(1)}}%)</p>
                <p>Benign: ${{stats.benign}} (${{(stats.benign/stats.total*100).toFixed(1)}}%)</p>
                <p>VUS: ${{stats.vus}} (${{(stats.vus/stats.total*100).toFixed(1)}}%)</p>
                <hr>
                <p>Rare (AF<0.1%): ${{stats.rare}} (${{(stats.rare/stats.total*100).toFixed(1)}}%)</p>
                <p>Common: ${{stats.common}} (${{(stats.common/stats.total*100).toFixed(1)}}%)</p>
            `);
        }}
    </script>
</body>
</html>
"""
        
        output_file = f"{gene}_comprehensive_variants.html"
        with open(output_file, 'w') as f:
            f.write(html_content)
        
        print(f"\nComprehensive visualization saved to: {output_file}")
        print(f"Visualizing {len(variants)} variants with {len(domains)} domains")
    
    def generate_gradient_legend(self) -> str:
        """Generate HTML for gradient legend"""
        return """
        <div class="gradient-legend">
            <p style="font-size: 12px; margin: 5px 0;">Color intensity = Rarity</p>
            <div style="display: flex; align-items: center;">
                <span style="font-size: 10px;">Common</span>
                <div class="gradient-bar" style="background: linear-gradient(to right, #ffcccc, #ff0000);"></div>
                <span style="font-size: 10px;">Ultra-rare</span>
            </div>
        </div>
        """

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gene', required=True, help='Gene symbol')
    parser.add_argument('--variant', help='Target variant (chr:pos:ref:alt)')
    parser.add_argument('--vcf', help='VCF file with target variants')
    parser.add_argument('--window', type=int, default=50, help='Window size (bp) for nearby variants')
    parser.add_argument('--radius', type=float, default=8.0, help='3D radius for nearby residues')
    parser.add_argument('--prefer-alphafold', action='store_true', help='Prefer AlphaFold structure')
    
    args = parser.parse_args()
    
    visualizer = ComprehensiveVariantVisualizer()
    
    if args.variant:
        await visualizer.process_variants(args.gene, args.variant, 'variant', 
                                        args.window, args.prefer_alphafold, args.radius)
    elif args.vcf:
        await visualizer.process_variants(args.gene, args.vcf, 'vcf',
                                        args.window, args.prefer_alphafold, args.radius)
    else:
        print("Provide --variant or --vcf")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
