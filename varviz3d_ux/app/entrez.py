import time
import xml.etree.ElementTree as ET
from http_session import session
from config import NCBI_TOOL, NCBI_EMAIL, NCBI_API_KEY, EFETCH_BATCH, REQUEST_TIMEOUT, NCBI_DELAY_SEC

def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i+n]

def fetch_entrez_abstracts(pmids):
    if not pmids: return []
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    abstracts = []
    for group in chunks(pmids, EFETCH_BATCH):
        params = {"db": "pubmed", "id": ",".join(group), "retmode": "xml",
                  "tool": NCBI_TOOL, "email": NCBI_EMAIL}
        if NCBI_API_KEY:
            params["api_key"] = NCBI_API_KEY
        r = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        root = ET.fromstring(r.text)
        for art in root.findall(".//PubmedArticle"):
            parts = [("".join(n.itertext())).strip() for n in art.findall(".//Abstract/AbstractText")]
            txt = " ".join([p for p in parts if p])
            if txt:
                abstracts.append(txt)
        if not getattr(r, "from_cache", False):
            time.sleep(NCBI_DELAY_SEC)
    return abstracts
