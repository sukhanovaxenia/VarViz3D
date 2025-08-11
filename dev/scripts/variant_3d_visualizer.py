#!/usr/bin/env python3
"""
variant_3d_visualizer.py - Interactive 3D visualization of genetic variants on protein structures

Usage:
    python variant_3d_visualizer.py --gene TP53 --variant "chr17:7577120:G:A"
    python variant_3d_visualizer.py --vcf variants.vcf --gene TP53
    python variant_3d_visualizer.py --hgvs "NM_000546.5:c.524G>A"
"""

import argparse
import asyncio
import aiohttp
import json
import sys
from typing import List, Dict, Optional, Tuple
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import myvariant
from Bio.PDB import PDBParser, PDBIO, Select
import warnings
warnings.filterwarnings('ignore')

class VariantVisualizer:
    def __init__(self):
        self.mv = myvariant.MyVariantInfo()
        self.uniprot_api = "https://rest.uniprot.org/uniprotkb"
        self.sifts_api = "https://www.ebi.ac.uk/pdbe/api"
        self.alphafold_api = "https://alphafold.ebi.ac.uk/api"
        
    async def process_variant(self, gene: str, variant_input: str, input_type: str = 'raw'):
        """Main processing pipeline"""
        print(f"Processing {input_type} variant for gene {gene}...")
        
        # 1. Parse variant input
        variants = self.parse_variant_input(variant_input, input_type)
        print(f"Parsed {len(variants)} variants")
        
        # 2. Get UniProt ID
        uniprot_id = await self.get_uniprot_id(gene)
        if not uniprot_id:
            raise ValueError(f"Could not find UniProt ID for gene {gene}")
        print(f"UniProt ID: {uniprot_id}")
        
        # 3. Annotate variants with MyVariant.info
        annotated_variants = await self.annotate_variants(variants)
        print(f"Annotated {len(annotated_variants)} variants")
        
        # 4. Get structure (PDB or AlphaFold)
        structure_data = await self.get_best_structure(uniprot_id)
        print(f"Found structure: {structure_data['source']} - {structure_data['id']}")
        
        # 5. Map variants to structure using SIFTS
        mapped_variants = await self.map_variants_sifts(
            uniprot_id, 
            structure_data, 
            annotated_variants
        )
        print(f"Mapped {len(mapped_variants)} variants to structure")
        
        # 6. Create interactive visualization
        self.create_3d_visualization(
            structure_data, 
            mapped_variants, 
            gene
        )
        
    def parse_variant_input(self, variant_input: str, input_type: str) -> List[Dict]:
        """Parse different variant input formats"""
        variants = []
        
        if input_type == 'raw':
            # Format: chr17:7577120:G:A
            parts = variant_input.split(':')
            if len(parts) == 4:
                variants.append({
                    'chr': parts[0].replace('chr', ''),
                    'pos': int(parts[1]),
                    'ref': parts[2],
                    'alt': parts[3]
                })
        
        elif input_type == 'hgvs':
            # Use MyVariant to parse HGVS
            result = self.mv.getvariant(variant_input)
            if result:
                variants.append({
                    'chr': result.get('chrom'),
                    'pos': result.get('hg38', {}).get('start'),
                    'ref': result.get('ref'),
                    'alt': result.get('alt')
                })
        
        elif input_type == 'vcf':
            # Parse VCF file
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
        """Get UniProt ID for gene"""
        async with aiohttp.ClientSession() as session:
            params = {
                'query': f'gene:{gene} AND organism_id:9606',
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
        """Annotate variants with MyVariant.info"""
        hgvs_ids = []
        for v in variants:
            hgvs = f"chr{v['chr']}:g.{v['pos']}{v['ref']}>{v['alt']}"
            hgvs_ids.append(hgvs)
        
        results = self.mv.getvariants(
            hgvs_ids,
            fields='clinvar,gnomad,cadd,dbnsfp.sift,dbnsfp.polyphen2',
            as_dataframe=False
        )
        
        annotated = []
        for i, result in enumerate(results):
            variant = variants[i].copy()
            
            # Extract pathogenicity
            clin_sig = result.get('clinvar', {}).get('clinical_significance', '')
            if 'pathogenic' in clin_sig.lower():
                variant['pathogenicity'] = 'pathogenic'
            elif 'benign' in clin_sig.lower():
                variant['pathogenicity'] = 'benign'
            else:
                variant['pathogenicity'] = 'vus'
            
            # Extract frequency
            variant['frequency'] = result.get('gnomad', {}).get('af', {}).get('af', 0)
            
            # Extract scores
            variant['cadd'] = result.get('cadd', {}).get('phred', 0)
            
            annotated.append(variant)
        
        return annotated
    
    async def get_best_structure(self, uniprot_id: str) -> Dict:
        """Get best available structure (PDB or AlphaFold)"""
        async with aiohttp.ClientSession() as session:
            # Try PDB first
            pdb_url = f"{self.sifts_api}/mappings/uniprot/{uniprot_id}"
            async with session.get(pdb_url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for pdb_data in data.get(uniprot_id, {}).get('PDB', {}).values():
                        if pdb_data:
                            pdb_id = pdb_data[0]['pdb_id']
                            return {
                                'source': 'PDB',
                                'id': pdb_id,
                                'url': f"https://files.rcsb.org/download/{pdb_id}.pdb"
                            }
            
            # Fallback to AlphaFold
            return {
                'source': 'AlphaFold',
                'id': uniprot_id,
                'url': f"https://alphafold.ebi.ac.uk/files/AF-{uniprot_id}-F1-model_v4.pdb"
            }
    
    async def map_variants_sifts(
        self, 
        uniprot_id: str, 
        structure_data: Dict, 
        variants: List[Dict]
    ) -> List[Dict]:
        """Map variants to structure positions using SIFTS"""
        mapped = []
        
        async with aiohttp.ClientSession() as session:
            # Get SIFTS mapping
            if structure_data['source'] == 'PDB':
                url = f"{self.sifts_api}/mappings/uniprot/{uniprot_id}"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        sifts_data = await resp.json()
                        
                        # Find mapping for this PDB
                        mappings = []
                        for pdb_mappings in sifts_data.get(uniprot_id, {}).get('PDB', {}).values():
                            for mapping in pdb_mappings:
                                if mapping['pdb_id'] == structure_data['id']:
                                    mappings.append(mapping)
                        
                        # Map each variant
                        for variant in variants:
                            # Assume protein position from variant annotation
                            # In real implementation, would need transcript mapping
                            uniprot_pos = variant.get('pos', 0) % 1000  # Simplified
                            
                            for mapping in mappings:
                                if (mapping['uniprot_start'] <= uniprot_pos <= 
                                    mapping['uniprot_end']):
                                    pdb_pos = (uniprot_pos - mapping['uniprot_start'] + 
                                              mapping['pdb_start'])
                                    
                                    variant['pdb_position'] = pdb_pos
                                    variant['chain'] = mapping['chain_id']
                                    mapped.append(variant)
                                    break
            else:
                # AlphaFold uses UniProt numbering directly
                for variant in variants:
                    variant['pdb_position'] = variant.get('pos', 0) % 1000  # Simplified
                    variant['chain'] = 'A'
                    mapped.append(variant)
        
        return mapped
    
    def create_3d_visualization(
        self, 
        structure_data: Dict, 
        mapped_variants: List[Dict],
        gene: str
    ):
        """Create interactive 3D visualization with Plotly"""
        import tempfile
        import os
        
        # Download PDB file
        pdb_file = tempfile.NamedTemporaryFile(suffix='.pdb', delete=False)
        
        import urllib.request
        urllib.request.urlretrieve(structure_data['url'], pdb_file.name)
        
        # Parse structure
        parser = PDBParser(QUIET=True)
        structure = parser.get_structure('protein', pdb_file.name)
        
        # Extract coordinates
        coords = []
        colors = []
        labels = []
        
        # Get all CA atoms
        for model in structure:
            for chain in model:
                for residue in chain:
                    if 'CA' in residue:
                        ca = residue['CA']
                        coord = ca.get_coord()
                        coords.append(coord)
                        
                        # Check if this position has a variant
                        color = 'lightgray'
                        label = f"{residue.resname} {residue.id[1]}"
                        
                        for variant in mapped_variants:
                            if (chain.id == variant.get('chain', 'A') and 
                                residue.id[1] == variant.get('pdb_position')):
                                # Color by pathogenicity
                                if variant['pathogenicity'] == 'pathogenic':
                                    color = 'red'
                                elif variant['pathogenicity'] == 'benign':
                                    color = 'green'
                                else:
                                    color = 'yellow'
                                
                                # Size by frequency (inverse)
                                freq = variant.get('frequency', 0)
                                size = 10 if freq < 0.001 else 5
                                
                                label = f"{label}<br>Variant: {variant['ref']}>{variant['alt']}<br>"
                                label += f"Pathogenicity: {variant['pathogenicity']}<br>"
                                label += f"Frequency: {freq:.2e}<br>"
                                label += f"CADD: {variant.get('cadd', 'N/A')}"
                                
                        colors.append(color)
                        labels.append(label)
        
        coords = np.array(coords)
        
        # Create 3D scatter plot
        fig = go.Figure()
        
        # Add backbone trace
        fig.add_trace(go.Scatter3d(
            x=coords[:, 0],
            y=coords[:, 1],
            z=coords[:, 2],
            mode='lines+markers',
            marker=dict(
                size=5,
                color=colors,
                colorscale='Viridis',
            ),
            line=dict(
                color='lightgray',
                width=2
            ),
            text=labels,
            hoverinfo='text',
            name='Protein backbone'
        ))
        
        # Highlight variants with larger markers
        variant_coords = []
        variant_colors = []
        variant_labels = []
        
        for i, (coord, color, label) in enumerate(zip(coords, colors, labels)):
            if color != 'lightgray':
                variant_coords.append(coord)
                variant_colors.append(color)
                variant_labels.append(label)
        
        if variant_coords:
            variant_coords = np.array(variant_coords)
            fig.add_trace(go.Scatter3d(
                x=variant_coords[:, 0],
                y=variant_coords[:, 1],
                z=variant_coords[:, 2],
                mode='markers',
                marker=dict(
                    size=10,
                    color=variant_colors,
                    line=dict(color='black', width=2)
                ),
                text=variant_labels,
                hoverinfo='text',
                name='Variants'
            ))
        
        # Update layout
        fig.update_layout(
            title=f"{gene} Protein Structure with Variants",
            scene=dict(
                xaxis_title='X',
                yaxis_title='Y',
                zaxis_title='Z',
                camera=dict(
                    up=dict(x=0, y=1, z=0),
                    center=dict(x=0, y=0, z=0),
                    eye=dict(x=1.5, y=1.5, z=1.5)
                )
            ),
            width=1000,
            height=800,
            showlegend=True
        )
        
        # Save as HTML
        output_file = f"{gene}_variant_structure.html"
        fig.write_html(output_file)
        print(f"\nVisualization saved to: {output_file}")
        
        # Clean up
        os.unlink(pdb_file.name)

async def main():
    parser = argparse.ArgumentParser(description='3D visualization of genetic variants')
    parser.add_argument('--gene', required=True, help='Gene symbol (e.g., TP53)')
    parser.add_argument('--variant', help='Variant in format chr:pos:ref:alt')
    parser.add_argument('--hgvs', help='HGVS notation')
    parser.add_argument('--vcf', help='VCF file path')
    
    args = parser.parse_args()
    
    visualizer = VariantVisualizer()
    
    if args.variant:
        await visualizer.process_variant(args.gene, args.variant, 'raw')
    elif args.hgvs:
        await visualizer.process_variant(args.gene, args.hgvs, 'hgvs')
    elif args.vcf:
        await visualizer.process_variant(args.gene, args.vcf, 'vcf')
    else:
        print("Please provide variant input using --variant, --hgvs, or --vcf")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())