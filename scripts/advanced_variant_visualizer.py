#!/usr/bin/env python3
"""
comprehensive_variant_visualizer.py - Visualize target variant and all nearby variants
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
        
        # 3. Get all variants in the region
        print(f"Fetching variants within {window_size}bp window...")
        all_variants = await self.get_nearby_variants(target_variant, window_size)
        print(f"Found {len(all_variants)} variants in region")
        
        # 4. Annotate all variants
        print("Annotating all variants...")
        annotated = await self.annotate_variants(all_variants)
        
        # 5. Add gradient colors
        colored_variants = self.assign_gradient_colors(annotated)
        
        # 6. Get structure
        structure_data = await self.get_best_structure(uniprot_id, prefer_alphafold)
        print(f"Structure: {structure_data['source']} - {structure_data['id']}")
        
        # 7. Map variants to structure
        mapped_variants = await self.map_variants_sifts(uniprot_id, structure_data, colored_variants)
        
        # 8. Mark target variant
        for v in mapped_variants:
            if (v['chr'] == target_variant['chr'] and 
                v['pos'] == target_variant['pos'] and
                v['ref'] == target_variant['ref'] and
                v['alt'] == target_variant['alt']):
                v['is_target'] = True
            else:
                v['is_target'] = False
        
        # 9. Create visualization
        self.create_comprehensive_visualization(gene, structure_data, mapped_variants, radius)
    
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
        
        # Add target variant if not in results
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
                                         variants: List[Dict], radius: float):
        """Create HTML with comprehensive variant visualization"""
        
        variants_js = json.dumps(variants)
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
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
        #container {{ display: flex; gap: 20px; }}
        #viewer {{ width: 800px; height: 600px; border: 1px solid #ccc; }}
        #controls {{ width: 350px; max-height: 600px; overflow-y: auto; }}
        .variant-info {{ margin: 5px 0; padding: 8px; border: 1px solid #ddd; cursor: pointer; font-size: 12px; }}
        .target-variant {{ border: 3px solid #000; font-weight: bold; }}
        button {{ margin: 5px; padding: 5px 10px; cursor: pointer; }}
        .legend {{ margin-top: 20px; }}
        .legend-item {{ display: flex; align-items: center; margin: 5px 0; }}
        .color-box {{ width: 20px; height: 20px; margin-right: 10px; border: 1px solid #000; }}
        .gradient-legend {{ margin: 10px 0; }}
        .gradient-bar {{ height: 20px; width: 200px; border: 1px solid #000; }}
        .stats {{ background: #f5f5f5; padding: 10px; margin: 10px 0; }}
    </style>
</head>
<body>
    <h1>{gene} Comprehensive Variant Structure Viewer</h1>
    <p>Structure: {structure_data['source']} ({structure_data['id']}) | Total variants: <span id="variant-count">{len(variants)}</span></p>
    
    <div id="container">
        <div id="viewer"></div>
        <div id="controls">
            <h3>View Options</h3>
            <button onclick="setStyle('cartoon')">Cartoon</button>
            <button onclick="setStyle('stick')">Stick</button>
            <button onclick="setStyle('sphere')">Sphere</button>
            <button onclick="setStyle('surface')">Surface</button>
            
            <h3>Highlight</h3>
            <button onclick="highlightAll()">All Variants</button>
            <button onclick="highlightPathogenic()">Pathogenic Only</button>
            <button onclick="highlightRare()">Rare Variants (AF<0.1%)</button>
            <button onclick="highlightTarget()">Target Variant</button>
            <button onclick="resetView()">Reset</button>
            
            <div class="stats">
                <h4>Variant Statistics</h4>
                <div id="stats-content"></div>
            </div>
            
            <div class="legend">
                <h3>Legend</h3>
                <h4>Pathogenicity</h4>
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
            
            <h3>All Variants ({len(variants)})</h3>
            <div id="variant-list"></div>
        </div>
    </div>
    
    <script>
        let viewer;
        let variants = {variants_js};
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
                common: 0
            }};
            
            variants.forEach(v => {{
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
                    viewer.setStyle({{}}, {{cartoon: {{color: 'lightgray', opacity: 0.7}}}});
                    highlightAll();
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
        }});
        
        function setStyle(style) {{
            viewer.setStyle({{}}, {{[style]: {{color: 'lightgray', opacity: 0.7}}}});
            highlightAll();
            viewer.render();
        }}
        
        function highlightAll() {{
            // Reset base structure
            viewer.setStyle({{}}, {{cartoon: {{color: 'lightgray', opacity: 0.7}}}});
            
            // Highlight all variants
            variants.forEach(function(variant) {{
                if (variant.pdb_position && variant.chain) {{
                    let size = variant.size || 1.0;
                    
                    viewer.setStyle(
                        {{chain: variant.chain, resi: variant.pdb_position}},
                        {{
                            cartoon: {{color: variant.color}},
                            stick: {{color: variant.color, radius: 0.3 * size}},
                            sphere: {{color: variant.color, radius: 0.8 * size}}
                        }}
                    );
                    
                    // Add label for target variant
                    if (variant.is_target) {{
                        viewer.addLabel(
                            "TARGET: " + variant.ref + variant.protein_position + variant.alt,
                            {{
                                position: {{chain: variant.chain, resi: variant.pdb_position}},
                                backgroundColor: 'black',
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
            viewer.setStyle({{}}, {{cartoon: {{color: 'lightgray', opacity: 0.7}}}});
            
            variants.forEach(function(variant) {{
                if (variant.pathogenicity === 'pathogenic' && variant.pdb_position) {{
                    viewer.setStyle(
                        {{chain: variant.chain, resi: variant.pdb_position}},
                        {{
                            cartoon: {{color: variant.color}},
                            sphere: {{color: variant.color, radius: 1.2}}
                        }}
                    );
                }}
            }});
            
            viewer.render();
        }}
        
        function highlightRare() {{
            viewer.setStyle({{}}, {{cartoon: {{color: 'lightgray', opacity: 0.7}}}});
            
            variants.forEach(function(variant) {{
                if (variant.frequency < 0.001 && variant.pdb_position) {{
                    viewer.setStyle(
                        {{chain: variant.chain, resi: variant.pdb_position}},
                        {{
                            cartoon: {{color: variant.color}},
                            sphere: {{color: variant.color, radius: 1.2}}
                        }}
                    );
                }}
            }});
            
            viewer.render();
        }}
        
        function highlightTarget() {{
            viewer.setStyle({{}}, {{cartoon: {{color: 'lightgray', opacity: 0.7}}}});
            
            let target = variants.find(v => v.is_target);
            if (target && target.pdb_position) {{
                // Highlight target
                viewer.setStyle(
                    {{chain: target.chain, resi: target.pdb_position}},
                    {{
                        cartoon: {{color: target.color}},
                        sphere: {{color: target.color, radius: 2.0}}
                    }}
                );
                
                // Show nearby
                viewer.setStyle(
                    {{
                        chain: target.chain, 
                        within: {{distance: radius, sel: {{chain: target.chain, resi: target.pdb_position}}}}
                    }},
                    {{
                        cartoon: {{color: 'orange', opacity: 0.8}},
                        stick: {{color: 'orange', radius: 0.2}}
                    }}
                );
                
                viewer.center({{chain: target.chain, resi: target.pdb_position}});
                viewer.zoom(0.8);
            }}
            
            viewer.render();
        }}
        
        function resetView() {{
            viewer.setStyle({{}}, {{cartoon: {{color: 'spectrum'}}}});
            viewer.zoomTo();
            viewer.render();
        }}
        
        function updateVariantList() {{
            let list = $('#variant-list');
            list.empty();
            
            // Sort variants by position
            let sortedVariants = [...variants].sort((a, b) => a.protein_position - b.protein_position);
            
            sortedVariants.forEach(function(variant, index) {{
                let div = $('<div>')
                    .addClass('variant-info')
                    .addClass(variant.is_target ? 'target-variant' : '')
                    .css('background-color', variant.color + '30') // 30% opacity
                    .html(`
                        <strong>${{variant.ref}}${{variant.protein_position}}${{variant.alt}}</strong>
                        ${{variant.is_target ? ' (TARGET)' : ''}}<br>
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
        
        function updateStats() {{
            let stats = calculateStats();
            $('#stats-content').html(`
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
        print(f"Visualizing {len(variants)} variants")
    
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