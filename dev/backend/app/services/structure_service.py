# backend/app/services/structure_service.py

import aiohttp
from typing import Optional, Dict

class StructureService:
    """Fetch structures from PDB or AlphaFold"""
    
    async def get_best_structure(self, gene: str, uniprot_id: Optional[str] = None):
        # Try PDB first
        pdb_data = await self._search_pdb(gene)
        if pdb_data:
            return {
                'source': 'PDB',
                'id': pdb_data['pdb_id'],
                'url': f"https://files.rcsb.org/download/{pdb_data['pdb_id']}.pdb",
                'viewer_url': f"https://www.rcsb.org/3d-view/{pdb_data['pdb_id']}"
            }
        
        # Fallback to AlphaFold
        if not uniprot_id:
            uniprot_id = await self._get_uniprot_id(gene)
        
        if uniprot_id:
            return {
                'source': 'AlphaFold',
                'id': uniprot_id,
                'url': f"https://alphafold.ebi.ac.uk/files/AF-{uniprot_id}-F1-model_v4.pdb",
                'viewer_url': f"https://alphafold.ebi.ac.uk/entry/{uniprot_id}",
                'confidence_url': f"https://alphafold.ebi.ac.uk/files/AF-{uniprot_id}-F1-confidence_v4.json"
            }
        
        return None
    
    async def _search_pdb(self, gene: str):
        """Search RCSB for structures"""
        url = "https://search.rcsb.org/rcsbsearch/v2/query"
        query = {
            "query": {
                "type": "terminal",
                "service": "text",
                "parameters": {
                    "value": gene,
                    "attribute": "rcsb_entity_source_organism.gene_name"
                }
            },
            "return_type": "entry"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=query) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('result_set'):
                        return {'pdb_id': data['result_set'][0]['identifier']}
        return None
    
    async def _get_uniprot_id(self, gene: str):
        """Get UniProt ID for gene"""
        url = f"https://rest.uniprot.org/uniprotkb/search?query=gene:{gene}+AND+organism_id:9606&format=json&size=1"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data['results']:
                        return data['results'][0]['primaryAccession']
        return None


# For variant mapping - use existing tools via their viewers
def get_structure_with_variant_highlights(structure_data: Dict, variants: list):
    """Generate viewer URLs with variant positions highlighted"""
    
    positions = [str(v.get('protein_position', '')) for v in variants if v.get('protein_position')]
    
    if structure_data['source'] == 'PDB':
        # RCSB Mol* viewer with selections
        selection = '+'.join(positions)
        viewer_url = f"{structure_data['viewer_url']}?preset=unitCell&sele={selection}"
    else:
        # AlphaFold viewer
        # Note: AlphaFold viewer doesn't support direct position highlighting via URL
        # But we can use Mol* viewer with AlphaFold structure
        af_pdb_url = structure_data['url']
        viewer_url = f"https://molstar.org/viewer/?structure-url={af_pdb_url}&select={','.join(positions)}"
    
    return {
        **structure_data,
        'viewer_url_with_variants': viewer_url,
        'variant_positions': positions
    }