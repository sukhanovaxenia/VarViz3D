# backend/app/services/structure_mapper.py

import asyncio
from typing import List, Dict, Optional, Tuple
import aiohttp
from Bio import PDB
import numpy as np
import logging

logger = logging.getLogger(__name__)

class StructureMapper:
    def __init__(self):
        self.pdb_api = "https://data.rcsb.org/rest/v1/core"
        self.alphafold_api = "https://alphafold.ebi.ac.uk/api"
        self.varmap_api = "https://www.ebi.ac.uk/thornton-srv/databases/cgi-bin/DisaStr/GetPage.pl"
        self.uniprot_api = "https://rest.uniprot.org/uniprotkb"
        
    async def get_structure_with_variants(
        self,
        gene_symbol: str,
        variants: List[Dict]
    ) -> Dict:
        """Get protein structure and map variants to 3D coordinates"""
        
        try:
            # Get UniProt ID for gene
            uniprot_id = await self._get_uniprot_id(gene_symbol)
            if not uniprot_id:
                logger.warning(f"No UniProt ID found for {gene_symbol}")
                return None
            
            # Try to get experimental structure first
            structure_data = await self._fetch_pdb_structure(uniprot_id)
            
            # Fallback to AlphaFold if no PDB structure
            if not structure_data:
                structure_data = await self._fetch_alphafold_structure(uniprot_id)
            
            if not structure_data:
                return None
            
            # Map variants to structure
            mapped_variants = await self._map_variants_to_structure(
                variants, structure_data, uniprot_id
            )
            
            return {
                "structure": structure_data,
                "mapped_variants": mapped_variants
            }
            
        except Exception as e:
            logger.error(f"Error in structure mapping: {str(e)}")
            return None
    
    async def _get_uniprot_id(self, gene_symbol: str) -> Optional[str]:
        """Get UniProt ID from gene symbol"""
        async with aiohttp.ClientSession() as session:
            query_url = f"{self.uniprot_api}/search"
            params = {
                'query': f'gene:{gene_symbol} AND organism_id:9606',
                'format': 'json',
                'size': 1
            }
            
            try:
                async with session.get(query_url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get('results'):
                            return data['results'][0]['primaryAccession']
            except Exception as e:
                logger.error(f"Error fetching UniProt ID: {e}")
                
        return None
    
    async def _fetch_pdb_structure(self, uniprot_id: str) -> Optional[Dict]:
        """Fetch PDB structure for UniProt ID"""
        async with aiohttp.ClientSession() as session:
            # Search for PDB entries
            search_url = f"{self.pdb_api}/uniprot/{uniprot_id}"
            
            try:
                async with session.get(search_url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data:
                            # Get the first PDB entry
                            pdb_id = data[0]['rcsb_id']
                            
                            # Fetch structure data
                            struct_url = f"https://files.rcsb.org/download/{pdb_id}.pdb"
                            async with session.get(struct_url) as struct_resp:
                                if struct_resp.status == 200:
                                    pdb_data = await struct_resp.text()
                                    
                                    return {
                                        'source': 'pdb',
                                        'structure_id': pdb_id,
                                        'pdb_data': pdb_data,
                                        'format': 'pdb'
                                    }
            except Exception as e:
                logger.error(f"Error fetching PDB structure: {e}")
                
        return None
    
    async def _fetch_alphafold_structure(self, uniprot_id: str) -> Optional[Dict]:
        """Fetch AlphaFold structure prediction"""
        async with aiohttp.ClientSession() as session:
            # AlphaFold API endpoint
            url = f"{self.alphafold_api}/prediction/{uniprot_id}"
            
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        if data and len(data) > 0:
                            entry = data[0]
                            
                            # Download PDB file
                            pdb_url = entry['pdbUrl']
                            async with session.get(pdb_url) as pdb_resp:
                                if pdb_resp.status == 200:
                                    pdb_data = await pdb_resp.text()
                                    
                                    return {
                                        'source': 'alphafold',
                                        'structure_id': entry['uniprotAccession'],
                                        'pdb_data': pdb_data,
                                        'format': 'pdb',
                                        'confidence': entry.get('confidenceVersion', 'v1')
                                    }
            except Exception as e:
                logger.error(f"Error fetching AlphaFold structure: {e}")
                
        return None
    
    async def _query_varmap(self, variant: Dict, uniprot_id: str) -> Optional[Dict]:
        """Query VarMap for variant mapping to structure
        Note: VarMap doesn't have a public API, so this is a simplified version
        """
        # In reality, you might need to:
        # 1. Use the web interface programmatically
        # 2. Contact EBI for API access
        # 3. Use alternative mapping like SIFTS
        
        # For now, we'll do simple position mapping
        protein_position = variant.get('protein_position')
        if not protein_position:
            return None
            
        # This is a placeholder - in production, you'd use proper mapping
        return {
            'uniprot_position': protein_position,
            'pdb_position': protein_position,  # Simplified - may differ in reality
            'chain': 'A',  # Default to chain A
            'coordinates': None  # Will be extracted from structure
        }
    
    async def _map_variants_to_structure(
        self,
        variants: List[Dict],
        structure_data: Dict,
        uniprot_id: str
    ) -> List[Dict]:
        """Map variants to 3D structure coordinates"""
        
        mapped = []
        
        # Parse PDB structure
        try:
            import io
            from Bio.PDB import PDBParser
            
            parser = PDBParser(QUIET=True)
            structure = parser.get_structure(
                'protein', 
                io.StringIO(structure_data['pdb_data'])
            )
            
            # Get first model
            model = structure[0]
            
            for variant in variants:
                if not variant.get('protein_position'):
                    continue
                
                # Try VarMap first (placeholder for now)
                mapping = await self._query_varmap(variant, uniprot_id)
                
                if mapping:
                    # Extract coordinates from structure
                    chain_id = mapping.get('chain', 'A')
                    position = mapping.get('pdb_position')
                    
                    if chain_id in model:
                        chain = model[chain_id]
                        
                        # Find residue
                        for residue in chain:
                            if residue.id[1] == position:
                                # Get CA atom coordinates
                                if 'CA' in residue:
                                    ca = residue['CA']
                                    coords = ca.get_coord()
                                    
                                    # Find nearby residues
                                    nearby = self._find_nearby_residues(
                                        coords, model, chain_id, distance=8.0
                                    )
                                    
                                    mapped.append({
                                        'variant': variant,
                                        'structure_position': {
                                            'x': float(coords[0]),
                                            'y': float(coords[1]),
                                            'z': float(coords[2])
                                        },
                                        'chain': chain_id,
                                        'nearby_residues': nearby
                                    })
                                    break
                                    
        except Exception as e:
            logger.error(f"Error parsing structure: {e}")
            
        return mapped

    async def map_variant_to_structure(gene, position):
        # 1. Get UniProt ID
        uniprot_resp = await fetch(f"https://rest.uniprot.org/uniprotkb/search?query=gene:{gene}")
        uniprot_id = uniprot_resp['results'][0]['primaryAccession']
        
        # 2. Get PDB mapping from SIFTS
        sifts_resp = await fetch(f"https://www.ebi.ac.uk/pdbe/api/mappings/uniprot/{uniprot_id}")
        # Returns exact UniProt→PDB position mapping
        
        return sifts_resp
    
    def _find_nearby_residues(
        self, 
        target_coords: np.ndarray,
        model: PDB.Model.Model,
        chain_id: str,
        distance: float = 8.0
    ) -> List[Dict]:
        """Find residues within distance of target coordinates"""
        
        nearby = []
        
        for chain in model:
            for residue in chain:
                if residue.id[0] != ' ':  # Skip heterogens
                    continue
                    
                # Get CA atom
                if 'CA' in residue:
                    ca = residue['CA']
                    coords = ca.get_coord()
                    
                    # Calculate distance
                    dist = np.linalg.norm(coords - target_coords)
                    
                    if dist <= distance and dist > 0:  # Exclude self
                        nearby.append({
                            'chain': chain.id,
                            'position': residue.id[1],
                            'residue': residue.resname,
                            'distance': round(float(dist), 2)
                        })
        
        # Sort by distance
        nearby.sort(key=lambda x: x['distance'])
        
        return nearby[:10]  # Return top 10 nearest
