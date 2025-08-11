import requests_cache
from config import NCBI_TOOL, NCBI_EMAIL

session = requests_cache.CachedSession("litvar_entrez_cache", expire_after=86400)
session.headers.update({
    "User-Agent": f"{NCBI_TOOL}/1.0 (+{NCBI_EMAIL})",
    "Accept": "application/xml,application/json;q=0.9,*/*;q=0.8"
})
