# backend/app/main.py
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import uvicorn

from .models import VariantInput, VariantAnnotation, VisualizationData
from .services.variant_annotator import VariantAnnotator
from .services.structure_mapper import StructureMapper
from .services.literature_miner import LiteratureMiner
from .services.cache_manager import CacheManager

app = FastAPI(
    title="VarViz3D API",
    description="Comprehensive genetic variant visualization API",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
variant_annotator = VariantAnnotator()
structure_mapper = StructureMapper()
literature_miner = LiteratureMiner()
cache_manager = CacheManager()

@app.post("/api/v1/analyze", response_model=VisualizationData)
async def analyze_variants(
    gene_symbol: str,
    variants: List[VariantInput],
    include_literature: bool = True,
    background_tasks: BackgroundTasks = None
):
    """Main endpoint for variant analysis and visualization data"""
    
    try:
        # Check cache first
        cache_key = f"{gene_symbol}:{hash(str(variants))}"
        cached_result = await cache_manager.get(cache_key)
        if cached_result:
            return cached_result
        
        # Annotate variants
        annotated_variants = await variant_annotator.annotate_batch(
            gene_symbol, variants
        )
        
        # Get protein structure and map variants
        structure_data = await structure_mapper.get_structure_with_variants(
            gene_symbol, annotated_variants
        )
        
        # Mine literature if requested
        literature_data = None
        if include_literature:
            literature_data = await literature_miner.find_variant_mentions(
                gene_symbol, annotated_variants
            )
        
        result = VisualizationData(
            gene=gene_symbol,
            variants=annotated_variants,
            structure=structure_data,
            literature=literature_data
        )
        
        # Cache result
        background_tasks.add_task(
            cache_manager.set, cache_key, result
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)