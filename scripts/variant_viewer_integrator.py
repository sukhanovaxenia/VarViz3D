#!/usr/bin/env python3
"""
variant_viewer_integrator.py - Integrate with existing advanced viewers
"""

import argparse
import asyncio
import webbrowser
from urllib.parse import quote

class VariantViewerIntegrator:
    
    def generate_mol_star_viewer(self, gene: str, pdb_id: str, variants: list):
        """Generate Mol* viewer URL with variants highlighted"""
        
        # Mol* supports complex selections via URL
        base_url = "https://molstar.org/viewer/"
        
        # Build selection string for variants
        selections = []
        for v in variants:
            if 'pdb_position' in v:
                selections.append(f"{v['chain']}/{v['pdb_position']}")
        
        params = {
            'structure-url': f'https://files.rcsb.org/download/{pdb_id}.pdb',
            'selection': ','.join(selections),
            'color': 'element'
        }
        
        # Build URL
        url = base_url + '?' + '&'.join([f"{k}={quote(str(v))}" for k, v in params.items()])
        
        return url
    
    def generate_ngl_viewer_html(self, gene: str, structure_id: str, variants: list):
        """Generate HTML with NGL viewer for full control"""
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{gene} Variant Viewer</title>
    <script src="https://unpkg.com/ngl@2.0.0-dev.37/dist/ngl.js"></script>
    <style>
        body {{ margin: 0; padding: 0; }}
        #viewport {{ width: 100vw; height: 100vh; }}
        #controls {{ position: absolute; top: 10px; right: 10px; background: white; padding: 10px; }}
    </style>
</head>
<body>
    <div id="viewport"></div>
    <div id="controls">
        <h3>{gene} Variants</h3>
        <button onclick="showCartoon()">Cartoon</button>
        <button onclick="showSurface()">Surface</button>
        <button onclick="showBallStick()">Ball+Stick</button>
        <button onclick="showContacts()">Show Contacts</button>
    </div>
    
    <script>
        var stage = new NGL.Stage("viewport");
        var structureComponent;
        var variants = {json.dumps(variants)};
        
        // Load structure
        stage.loadFile("rcsb://{structure_id}").then(function(component) {{
            structureComponent = component;
            
            // Default representation
            component.addRepresentation("cartoon", {{
                color: "chainindex"
            }});
            
            // Highlight variants
            variants.forEach(function(v) {{
                if (v.pdb_position) {{
                    var selection = v.chain + ":" + v.pdb_position;
                    
                    // Add sphere for variant
                    component.addRepresentation("ball+stick", {{
                        sele: selection,
                        color: getVariantColor(v.pathogenicity)
                    }});
                    
                    // Show nearby residues
                    component.addRepresentation("licorice", {{
                        sele: selection + " around 5",
                        color: "element",
                        opacity: 0.5
                    }});
                }}
            }});
            
            component.autoView();
        }});
        
        function getVariantColor(pathogenicity) {{
            switch(pathogenicity) {{
                case 'pathogenic': return 'red';
                case 'benign': return 'green';
                default: return 'yellow';
            }}
        }}
        
        function showCartoon() {{
            structureComponent.removeAllRepresentations();
            structureComponent.addRepresentation("cartoon", {{color: "chainindex"}});
            highlightVariants();
        }}
        
        function showSurface() {{
            structureComponent.removeAllRepresentations();
            structureComponent.addRepresentation("surface", {{
                opacity: 0.7,
                color: "hydrophobicity"
            }});
            highlightVariants();
        }}
        
        function showContacts() {{
            structureComponent.addRepresentation("contact", {{
                contactType: "polar",
                color: "skyblue"
            }});
        }}
        
        function highlightVariants() {{
            variants.forEach(function(v) {{
                if (v.pdb_position) {{
                    structureComponent.addRepresentation("spacefill", {{
                        sele: v.chain + ":" + v.pdb_position,
                        color: getVariantColor(v.pathogenicity)
                    }});
                }}
            }});
        }}
        
        // Handle window resize
        window.addEventListener("resize", function() {{
            stage.handleResize();
        }}, false);
    </script>
</body>
</html>
"""
        
        with open(f"{gene}_ngl_viewer.html", 'w') as f:
            f.write(html)
        
        return f"{gene}_ngl_viewer.html"
    
    def generate_mutation_explorer_link(self, gene: str, variants: list):
        """Generate link to MutationExplorer-style viewer"""
        
        # For genes with known structures in their database
        base_url = f"https://mutationexplorer.vda-group.de/mutation_explorer/gene/{gene.lower()}"
        
        # Add variant parameters if their API supports it
        variant_params = []
        for v in variants:
            if 'protein_position' in v:
                variant_params.append(f"p.{v['ref']}{v['protein_position']}{v['alt']}")
        
        if variant_params:
            url = f"{base_url}?variants={','.join(variant_params)}"
        else:
            url = base_url
            
        return url
    
    def generate_proteinpaint_embed(self, gene: str):
        """Generate ProteinPaint embed code"""
        
        return f"""
<iframe 
    src="https://proteinpaint.stjude.org/?genome=hg38&gene={gene}"
    width="100%" 
    height="800px"
    frameborder="0">
</iframe>
"""

# Alternative: Use existing web services directly
def generate_web_links(gene: str, variants: list):
    """Generate links to existing visualization services"""
    
    links = {
        'MutationMapper': f'https://www.cbioportal.org/mutation_mapper?standaloneMutationMapperGeneTab={gene}',
        'ProteinPaint': f'https://proteinpaint.stjude.org/?gene={gene}',
        'COSMIC 3D': f'https://cancer.sanger.ac.uk/cosmic3d/protein/transcript/{gene}',
        'VarSome': f'https://varsome.com/gene/hg38/{gene}',
        'gnomAD': f'https://gnomad.broadinstitute.org/gene/{gene}?dataset=gnomad_r4'
    }
    
    return links

if __name__ == "__main__":
    import json
    
    # Example usage
    gene = "TP53"
    variants = [
        {"pdb_position": 175, "chain": "A", "pathogenicity": "pathogenic", "ref": "R", "alt": "H"},
        {"pdb_position": 248, "chain": "A", "pathogenicity": "pathogenic", "ref": "R", "alt": "Q"}
    ]
    
    integrator = VariantViewerIntegrator()
    
    # Option 1: Generate NGL viewer
    html_file = integrator.generate_ngl_viewer_html(gene, "1TUP", variants)
    print(f"Generated: {html_file}")
    
    # Option 2: Use existing services
    links = generate_web_links(gene, variants)
    print("\nAlternative viewers:")
    for name, url in links.items():
        print(f"{name}: {url}")