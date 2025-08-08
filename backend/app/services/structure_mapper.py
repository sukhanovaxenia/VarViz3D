# backend/app/services/structure_mapper.py
import asyncio
from typing import List, Dict, Optional, Tuple
import aiohttp
from Bio import PDB
import numpy as np

class StructureMapper:
    def __init__(self):
        self.pdb_api = "https://data.rcsb.org/rest/v1/core"
        self.alphafold_api = "https://alphafold.ebi.ac.uk/api"
        self.varmap_api = "https://www.ebi.ac.uk/thornton-group/varmap/api"
        
    async def get_structure_with_variants(
        self,
        gene_symbol: str,
        variants: List[VariantAnnotation]
    ) -> Dict:
        """Get protein structure and map variants to 3D coordinates"""
        
        # Get UniProt ID for gene
        uniprot_id = await self._get_uniprot_id(gene_symbol)
        
        # Try to get experimental structure first
        structure_data = await self._fetch_pdb_structure(uniprot_id)
        
        # Fallback to AlphaFold if no PDB structure
        if not structure_data:
            structure_data = await self._fetch_alphafold_structure(uniprot_id)
        
        if not structure_data:
            return None
        
        # Map variants to structure
        mapped_variants = await self._map_variants_to_structure(
            variants, structure_data
        )
        
        return {
            "structure": structure_data,
            "mapped_variants": mapped_variants
        }
    
    async def _map_variants_to_structure(
        self,
        variants: List[VariantAnnotation],
        structure_data: Dict
    ) -> List[MappedVariant]:
        """Map variants to 3D coordinates using VarMap"""
        
        mapped = []
        for variant in variants:
            if not variant.protein_position:
                continue
                
            # Use VarMap API for accurate mapping
            mapping = await self._query_varmap(variant)
            
            if mapping:
                coords = mapping.get("coordinates", {})
                mapped.append(MappedVariant(
                    variant=variant,
                    structure_position={
                        "x": coords.get("x"),
                        "y": coords.get("y"),
                        "z": coords.get("z")
                    },
                    nearby_residues=self._find_nearby_residues(
                        coords, structure_data
                    )
                ))
        
        return mapped