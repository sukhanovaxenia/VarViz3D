# literature_agent.py
"""Literature Agent - interfaces with FastAPI backend for variant literature analysis"""

import requests
from typing import Dict, List, Optional

class LiteratureAgent:
    """Complete literature analysis agent using your FastAPI backend"""
    
    def __init__(self, api_base="http://localhost:8000"):
        self.api_base = api_base
        self.session = requests.Session()
    
    def get_rsid_literature(self, rsid: str, gene: str = None, 
                           variant_hint: str = None, sample_size: int = 10) -> Dict:
        """
        Get literature summary for an rsID using your pipeline
        """
        try:
            params = {"sample": sample_size}
            if gene:
                params["gene"] = gene
            if variant_hint:
                params["variant_hint"] = variant_hint
            
            r = self.session.get(
                f"{self.api_base}/api/rsids/{rsid}/detail",
                params=params,
                timeout=30
            )
            
            if r.ok:
                return r.json()
            return {
                "error": f"API error: {r.status_code}",
                "rsid": rsid,
                "abstract_count": 0,
                "sampled_pmids": 0,
                "functional_answer": "API error occurred"
            }
        except Exception as e:
            return {
                "error": str(e),
                "rsid": rsid,
                "abstract_count": 0,
                "sampled_pmids": 0,
                "functional_answer": f"Connection error: {e}"
            }
    
    def get_pmid_counts(self, rsids: List[str]) -> Dict[str, int]:
        """
        Get PMID counts for multiple rsIDs via LitVar
        """
        try:
            r = self.session.post(
                f"{self.api_base}/api/litvar/pmid_counts",
                json={"rsids": rsids},
                timeout=30
            )
            
            if r.ok:
                data = r.json()
                return data.get("counts", {})
            return {}
        except Exception as e:
            print(f"Error getting PMID counts: {e}")
            return {}
    
    def get_gene_overview(self, gene: str, dataset: str = "gnomad_r4", 
                         ref: str = "GRCh38") -> Dict:
        """
        Get gene overview with MyGene summary and gnomAD variants
        """
        try:
            params = {
                "gene": gene,
                "dataset": dataset,
                "ref": ref
            }
            
            r = self.session.get(
                f"{self.api_base}/api/gene/overview",
                params=params,
                timeout=30
            )
            
            if r.ok:
                return r.json()
            return {"error": f"API error: {r.status_code}"}
        except Exception as e:
            return {"error": str(e)}
    
    def batch_analyze_variants(self, rsids: List[str], gene: str = None, 
                              max_variants: int = 20) -> List[Dict]:
        """
        Analyze multiple variants - get literature for top variants by PMID count
        """
        results = []
        
        # First get PMID counts
        counts = self.get_pmid_counts(rsids[:max_variants])
        
        # Sort by count and analyze top ones
        sorted_rsids = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        
        for rsid, count in sorted_rsids[:5]:  # Analyze top 5
            if count > 0:
                result = self.get_rsid_literature(rsid, gene=gene, sample_size=min(count, 20))
                result['pmid_count'] = count
                results.append(result)
        
        return results