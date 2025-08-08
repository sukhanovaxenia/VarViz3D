# backend/app/services/variant_annotator.py
import asyncio
from typing import List, Dict, Optional
import aiohttp
from myvariant import MyVariantInfo
import logging

logger = logging.getLogger(__name__)

class VariantAnnotator:
    def __init__(self):
        self.mv = MyVariantInfo()
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def annotate_batch(
        self, 
        gene_symbol: str, 
        variants: List[VariantInput]
    ) -> List[VariantAnnotation]:
        """Annotate a batch of variants with comprehensive information"""
        
        # Convert to HGVS format
        hgvs_ids = [self._to_hgvs(v) for v in variants]
        
        # Batch query to MyVariant.info
        annotations = await self._batch_query_myvariant(hgvs_ids)
        
        # Enhance with additional sources
        enhanced_annotations = []
        for variant, base_annot in zip(variants, annotations):
            enhanced = await self._enhance_annotation(
                variant, base_annot, gene_symbol
            )
            enhanced_annotations.append(enhanced)
        
        return enhanced_annotations
    
    def _to_hgvs(self, variant: VariantInput) -> str:
        """Convert variant to HGVS format"""
        return f"chr{variant.chromosome}:g.{variant.position}{variant.reference}>{variant.alternate}"
    
    async def _batch_query_myvariant(self, hgvs_ids: List[str]) -> List[Dict]:
        """Query MyVariant.info in batches"""
        fields = [
            "clinvar", "gnomad", "cadd", "dbnsfp.sift",
            "dbnsfp.polyphen2", "dbnsfp.phylop", "dbnsfp.gerp"
        ]
        
        # MyVariant.info handles up to 1000 variants per query
        results = []
        for i in range(0, len(hgvs_ids), 100):
            batch = hgvs_ids[i:i+100]
            batch_results = self.mv.getvariants(
                batch, 
                fields=",".join(fields),
                as_dataframe=False
            )
            results.extend(batch_results)
        
        return results
    
    async def _enhance_annotation(
        self, 
        variant: VariantInput,
        base_annot: Dict,
        gene_symbol: str
    ) -> VariantAnnotation:
        """Enhance annotation with additional data sources"""
        
        # Extract scores and predictions
        annotation = VariantAnnotation(
            input=variant,
            hgvs_g=base_annot.get("_id", ""),
            gene_symbol=gene_symbol,
            transcript_id=base_annot.get("transcript", ""),
            variant_type=self._determine_variant_type(variant),
            
            # Clinical significance
            pathogenicity=self._determine_pathogenicity(base_annot),
            clinvar_id=base_annot.get("clinvar", {}).get("variant_id"),
            clinical_significance=base_annot.get("clinvar", {}).get(
                "clinical_significance"
            ),
            
            # Population frequency
            gnomad_af=base_annot.get("gnomad", {}).get("af", {}).get("af"),
            gnomad_af_popmax=base_annot.get("gnomad", {}).get("af", {}).get(
                "af_popmax"
            ),
            
            # Prediction scores
            cadd_score=base_annot.get("cadd", {}).get("phred"),
            sift_score=base_annot.get("dbnsfp", {}).get("sift", {}).get("score"),
            polyphen_score=base_annot.get("dbnsfp", {}).get(
                "polyphen2", {}
            ).get("hdiv", {}).get("score"),
            
            # Conservation
            phylop_score=base_annot.get("dbnsfp", {}).get("phylop", {}).get(
                "100way_vertebrate"
            ),
            gerp_score=base_annot.get("dbnsfp", {}).get("gerp", {}).get("rs")
        )
        
        # Add protein-level annotations
        if annotation.transcript_id:
            protein_annot = await self._get_protein_annotations(
                gene_symbol, annotation
            )
            annotation.protein_position = protein_annot.get("position")
            annotation.amino_acid_change = protein_annot.get("aa_change")
            annotation.protein_domain = protein_annot.get("domain")
            annotation.affected_go_terms = protein_annot.get("go_terms")
        
        return annotation