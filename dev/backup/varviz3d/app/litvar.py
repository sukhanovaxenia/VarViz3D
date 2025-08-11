from http_session import session
from config import REQUEST_TIMEOUT

def get_pmids_from_rsids(rsids):
    url = "https://www.ncbi.nlm.nih.gov/research/bionlp/litvar/api/v1/public/rsids2pmids"
    r = session.get(url, params={"rsids": ",".join(rsids)}, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict):
        return {k: list(map(str, v or [])) for k, v in data.items()}
    out = {}
    for d in (data or []):
        if isinstance(d, dict) and d.get("rsid"):
            out.setdefault(d["rsid"], []).extend(map(str, d.get("pmids", []) or []))
    return out
