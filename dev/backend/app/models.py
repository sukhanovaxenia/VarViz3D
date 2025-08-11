# backend/app/models.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime

class VariantType(str, Enum):
    SNV = "single_nucleotide_variant"
    INSERTION = "insertion"
    DELETION = "deletion"
    INDEL = "indel"

class PathogenicityLevel(str, Enum):
    PATHOGENIC = "pathogenic"
    LIKELY_PATHOGENIC = "likely_pathogenic"
    VUS = "uncertain_significance"
    LIKELY_BENIGN = "likely_benign"
    BENIGN = "benign"

class VariantInput(BaseModel):
    chromosome: str = Field(..., example="17")
    position: int = Field(..., example=7577120)
    reference: str = Field(..., example="G")
    alternate: str = Field(..., example="A")
    
class VariantAnnotation(BaseModel):
    # Basic info
    input: VariantInput
    hgvs_g: str
    hgvs_p: Optional[str]
    variant_type: VariantType
    
    # Annotations
    gene_symbol: str
    transcript_id: str
    protein_position: Optional[int]
    amino_acid_change: Optional[str]
    
    # Clinical significance
    pathogenicity: Optional[PathogenicityLevel]
    clinvar_id: Optional[str]
    clinical_significance: Optional[str]
    
    # Population frequency
    gnomad_af: Optional[float]
    gnomad_af_popmax: Optional[float]
    
    # Functional predictions
    cadd_score: Optional[float]
    sift_score: Optional[float]
    polyphen_score: Optional[float]
    
    # Conservation
    phylop_score: Optional[float]
    gerp_score: Optional[float]
    
    # Protein context
    protein_domain: Optional[Dict[str, Any]]
    secondary_structure: Optional[str]
    solvent_accessibility: Optional[float]
    
    # GO annotations
    affected_go_terms: Optional[List[Dict[str, str]]]

class ProteinStructure(BaseModel):
    source: str  # "pdb" or "alphafold"
    structure_id: str
    resolution: Optional[float]
    chain_id: str
    sequence: str
    domains: List[Dict[str, Any]]
    
class MappedVariant(BaseModel):
    variant: VariantAnnotation
    structure_position: Dict[str, float]  # x, y, z coordinates
    nearby_residues: List[Dict[str, Any]]
    
class VisualizationData(BaseModel):
    gene: str
    variants: List[VariantAnnotation]
    structure: Optional[ProteinStructure]
    mapped_variants: Optional[List[MappedVariant]]
    literature: Optional[List[Dict[str, Any]]]
    timestamp: datetime = Field(default_factory=datetime.now)