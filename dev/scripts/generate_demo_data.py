#!/usr/bin/env python3
# scripts/generate_demo_data.py

import json
import random
from datetime import datetime

# Common pathogenic variants for demo
DEMO_VARIANTS = {
    "TP53": [
        {"chr": "17", "pos": 7577120, "ref": "G", "alt": "A", "aa": "R175H", "path": "pathogenic"},
        {"chr": "17", "pos": 7577538, "ref": "C", "alt": "T", "aa": "R248Q", "path": "pathogenic"},
        {"chr": "17", "pos": 7577121, "ref": "C", "alt": "T", "aa": "R273H", "path": "pathogenic"},
        {"chr": "17", "pos": 7578406, "ref": "C", "alt": "T", "aa": "Y220C", "path": "likely_pathogenic"},
        {"chr": "17", "pos": 7578442, "ref": "T", "alt": "C", "aa": "G245S", "path": "uncertain_significance"},
    ],
    "BRCA1": [
        {"chr": "17", "pos": 41246747, "ref": "A", "alt": "G", "aa": "D67G", "path": "pathogenic"},
        {"chr": "17", "pos": 41244936, "ref": "G", "alt": "T", "aa": "E143*", "path": "pathogenic"},
        {"chr": "17", "pos": 41245466, "ref": "G", "alt": "A", "aa": "C61Y", "path": "likely_pathogenic"},
    ],
    "EGFR": [
        {"chr": "7", "pos": 55259515, "ref": "T", "alt": "G", "aa": "L858R", "path": "pathogenic"},
        {"chr": "7", "pos": 55242464, "ref": "AGGAATTAAGAGAAGC", "alt": "A", "aa": "E746_A750del", "path": "pathogenic"},
        {"chr": "7", "pos": 55249071, "ref": "C", "alt": "T", "aa": "T790M", "path": "likely_pathogenic"},
    ]
}

def generate_demo_vcf(gene="TP53", output_file="demo_variants.vcf"):
    """Generate a demo VCF file"""
    
    header = """##fileformat=VCFv4.2
##fileDate={}
##source=VarViz3D_Demo
##reference=GRCh38
##INFO=<ID=GENE,Number=1,Type=String,Description="Gene symbol">
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
""".format(datetime.now().strftime("%Y%m%d"))
    
    with open(output_file, 'w') as f:
        f.write(header)
        
        variants = DEMO_VARIANTS.get(gene, DEMO_VARIANTS["TP53"])
        for var in variants:
            line = f"{var['chr']}\t{var['pos']}\t.\t{var['ref']}\t{var['alt']}\t.\tPASS\tGENE={gene}\n"
            f.write(line)
    
    print(f"Generated demo VCF: {output_file}")

def generate_demo_json(gene="TP53", output_file="demo_variants.json"):
    """Generate demo JSON data"""
    
    variants = DEMO_VARIANTS.get(gene, DEMO_VARIANTS["TP53"])
    
    demo_data = {
        "gene": gene,
        "variants": [
            {
                "chromosome": v["chr"],
                "position": v["pos"],
                "reference": v["ref"],
                "alternate": v["alt"],
                "amino_acid_change": v.get("aa", ""),
                "pathogenicity": v.get("path", "uncertain_significance"),
                "cadd_score": random.uniform(15, 35) if v.get("path") == "pathogenic" else random.uniform(5, 20),
                "gnomad_af": random.uniform(0.00001, 0.001) if v.get("path") != "pathogenic" else 0.0,
            }
            for v in variants
        ],
        "demo": True,
        "generated_at": datetime.now().isoformat()
    }
    
    with open(output_file, 'w') as f:
        json.dump(demo_data, f, indent=2)
    
    print(f"Generated demo JSON: {output_file}")

if __name__ == "__main__":
    import sys
    
    gene = sys.argv[1] if len(sys.argv) > 1 else "TP53"
    
    generate_demo_vcf(gene, f"demo_data/{gene}_demo.vcf")
    generate_demo_json(gene, f"demo_data/{gene}_demo.json")