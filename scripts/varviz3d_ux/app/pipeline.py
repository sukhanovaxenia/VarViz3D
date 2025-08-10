import random
from litvar import get_pmids_from_rsids
from entrez import fetch_entrez_abstracts
from functional_summary import summarize_functional_effect
from config import SAMPLE_PMIDS
from textutil import FUNC_WORDS

def rsid_answer(rsid, gene_hint=None, variant_hint=None):
    mapping = get_pmids_from_rsids([rsid])
    all_pmids = sorted({p for v in mapping.values() for p in v})
    if not all_pmids:
        return {"rsid": rsid, "abstract_count": 0, "sampled_pmids": 0, "functional_answer": "No PMIDs found."}

    sample = random.sample(all_pmids, min(SAMPLE_PMIDS, len(all_pmids)))
    abstracts = fetch_entrez_abstracts(sample)

    functional_abstracts = [a for a in abstracts if FUNC_WORDS.search(a)]
    pool = functional_abstracts or abstracts
    if not pool:
        return {"rsid": rsid, "abstract_count": len(abstracts), "sampled_pmids": len(sample), "functional_answer": "No abstracts found."}

    k = min(8, len(pool))
    combined = "\n\n".join(random.sample(pool, k))
    answer = summarize_functional_effect(combined, max_sentences=2, gene_hint=gene_hint, variant_hint=variant_hint)

    return {
        "rsid": rsid,
        "gene": gene_hint,
        "abstract_count": len(abstracts),
        "sampled_pmids": len(sample),
        "functional_answer": answer
    }
