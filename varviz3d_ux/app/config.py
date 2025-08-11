import os

NCBI_TOOL = "gene_variant_summarizer"
NCBI_EMAIL = os.getenv("NCBI_EMAIL", "your_email@example.com")
NCBI_API_KEY = os.getenv("NCBI_API_KEY", "")
SAMPLE_PMIDS = int(os.getenv("SAMPLE_PMIDS", 10))
EFETCH_BATCH = int(os.getenv("EFETCH_BATCH", 128))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", 30))
NCBI_DELAY_SEC = float(os.getenv("NCBI_DELAY_SEC", 0.34))
