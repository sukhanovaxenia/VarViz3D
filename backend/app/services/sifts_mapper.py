# backend/app/services/sifts_mapper.py
# Real working integration with SIFTS API

import aiohttp
import asyncio
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class SIFTSMapper:
    """Use SIFTS API for UniProt to PDB mapping"""
    
    def __init__(self):
        self.base_url = "https://www.ebi.ac.uk/pdbe/api"
        self.uniprot_api = "https://rest.uniprot.org/uniprotkb"
        
    async def get_structure_mappings(
        self, 
        gene_symbol: str,
        variants: List[Dict]
    ) -> Dict:
        """Get all available structure mappings for a gene"""
        
        # Step 1: Gene → UniProt ID
        uniprot_id = await self._get_uniprot_id(gene_symbol)
        if not uniprot_id:
            return None
            
        # Step 2: UniProt → PDB mappings via SIFTS
        mappings = await self._get_sifts_mappings(uniprot_id)
        
        # Step 3: Map variants to structures
        mapped_variants = self._map_variants_to_structures(
            variants, mappings, uniprot_id
        )
        
        # Step 4: Get best PDB structure
        best_structure = self._select_best_structure(mappings)
        
        return {
            "uniprot_id": uniprot_id,
            "mappings": mappings,
            "best_structure": best_structure,
            "mapped_variants": mapped_variants
        }
    
    async def _get_uniprot_id(self, gene_symbol: str) -> Optional[str]:
        """Get UniProt ID from gene symbol"""
        async with aiohttp.ClientSession() as session:
            params = {
                'query': f'(gene:{gene_symbol}) AND (organism_id:9606)',
                'format': 'json',
                'size': 1
            }
            
            async with session.get(f"{self.uniprot_api}/search", params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('results'):
                        return data['results'][0]['primaryAccession']
        return None
    
    async def _get_sifts_mappings(self, uniprot_id: str) -> List[Dict]:
        """Get all PDB mappings from SIFTS"""
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/mappings/uniprot/{uniprot_id}"
            
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    # Parse SIFTS response
                    mappings = []
                    for pdb_data in data.get(uniprot_id, {}).get('PDB', {}).values():
                        for mapping in pdb_data:
                            mappings.append({
                                'pdb_id': mapping['pdb_id'],
                                'chain': mapping['chain_id'],
                                'resolution': mapping.get('resolution'),
                                'method': mapping.get('experimental_method'),
                                'uniprot_start': mapping['uniprot_start'],
                                'uniprot_end': mapping['uniprot_end'],
                                'pdb_start': mapping['pdb_start'], 
                                'pdb_end': mapping['pdb_end'],
                                'coverage': mapping['uniprot_end'] - mapping['uniprot_start']
                            })
                    
                    return sorted(mappings, key=lambda x: x.get('resolution', 999))
        return []
    
    def _map_variants_to_structures(
        self, 
        variants: List[Dict],
        mappings: List[Dict],
        uniprot_id: str
    ) -> List[Dict]:
        """Map variants to available PDB structures"""
        
        mapped = []
        
        for variant in variants:
            pos = variant.get('protein_position')
            if not pos:
                continue
                
            # Find all structures covering this position
            covering_structures = []
            
            for mapping in mappings:
                if mapping['uniprot_start'] <= pos <= mapping['uniprot_end']:
                    # Calculate PDB position
                    pdb_pos = pos - mapping['uniprot_start'] + mapping['pdb_start']
                    
                    covering_structures.append({
                        'pdb_id': mapping['pdb_id'],
                        'chain': mapping['chain'],
                        'pdb_position': pdb_pos,
                        'resolution': mapping.get('resolution', 999)
                    })
            
            mapped.append({
                'variant': variant,
                'uniprot_position': pos,
                'structures': sorted(
                    covering_structures, 
                    key=lambda x: x['resolution']
                )
            })
        
        return mapped
    
    def _select_best_structure(self, mappings: List[Dict]) -> Optional[Dict]:
        """Select best structure based on resolution and coverage"""
        if not mappings:
            return None
            
        # Prefer X-ray structures with good resolution
        xray = [m for m in mappings if m.get('method') == 'X-ray diffraction']
        if xray:
            return xray[0]  # Already sorted by resolution
            
        # Otherwise, return best resolution
        return mappings[0]


# Simplified version for immediate use
async def quick_sifts_mapping(gene: str, position: int) -> Optional[Dict]:
    """Quick helper function for single variant mapping"""
    
    mapper = SIFTSMapper()
    
    # Get UniProt ID
    uniprot_id = await mapper._get_uniprot_id(gene)
    if not uniprot_id:
        return None
        
    # Get mappings
    mappings = await mapper._get_sifts_mappings(uniprot_id)
    
    # Find structures covering this position
    for mapping in mappings:
        if mapping['uniprot_start'] <= position <= mapping['uniprot_end']:
            pdb_pos = position - mapping['uniprot_start'] + mapping['pdb_start']
            
            return {
                'uniprot_id': uniprot_id,
                'uniprot_position': position,
                'pdb_id': mapping['pdb_id'],
                'chain': mapping['chain'],
                'pdb_position': pdb_pos,
                'structure_url': f"https://files.rcsb.org/download/{mapping['pdb_id']}.pdb"
            }
    
    return None
