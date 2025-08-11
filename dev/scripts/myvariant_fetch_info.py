import requests, math, time

# ---------- утилиты ----------
def _get_json(url, params=None, sleep=0.34):
    # простая защита от rate-limit (3 req/сек для E-utilities без api_key)
    r = requests.get(url, params=params, timeout=60)
    if sleep: time.sleep(sleep)
    r.raise_for_status()
    return r.json()

def _row(chrom, start, end, ref, alt, source, extra):
    return {
        "chrom": str(chrom).replace("chr",""),
        "start": int(start) if start is not None else None,
        "end": int(end) if end is not None else None,
        "ref": ref,
        "alt": alt,
        "source": source,
        **extra
    }

# ---------- MyVariant: всё сразу в hg38 ----------
def fetch_myvariant_by_gene_hg38(gene, size=1000):
    url = "https://myvariant.info/v1/query"
    q = f"gene:{gene}"
    fields = ",".join([
        "dbsnp.rsid",
        "clinvar.rcv", "clinvar.rcv.clinical_significance", "clinvar.vcf",
        "genomic.hg38", "allele",
    ])
    params = {
        "q": q,
        "fields": fields,
        "size": size,
        "species": "human",
        "assembly": "hg38",
    }
    out = []
    j = _get_json(url, params=params, sleep=0)  # их API обычно без строгого rate-limit
    for hit in j.get("hits", []):
        # координаты в genomic.hg38 (иногда список, иногда объект)
        g38 = hit.get("genomic", {}).get("hg38")
        if not g38:
            continue
        g38list = g38 if isinstance(g38, list) else [g38]
        rsid = hit.get("dbsnp", {}).get("rsid")
        # clinvar summary
        clinsig = None
        if "clinvar" in hit:
            # пробуем достать сводную клин.значимость
            # в разных версиях поле может жить в rcv[*].clinical_significance.description
            rcv = hit["clinvar"].get("rcv") or []
            if isinstance(rcv, dict): rcv = [rcv]
            for r in rcv:
                d = r.get("clinical_significance", {}).get("description")
                if d:
                    clinsig = d
                    break
        for loc in g38list:
            chrom = loc.get("chr") or loc.get("chrom")
            start = loc.get("start")
            end = loc.get("end")
            ref = loc.get("ref") or (hit.get("clinvar", {}).get("vcf", {}).get("ref"))
            alt = loc.get("alt") or (hit.get("clinvar", {}).get("vcf", {}).get("alt"))
            if chrom and start is not None:
                out.append(_row(chrom, start, end or start, ref, alt, "myvariant", {
                    "rsid": rsid, "clinvar_significance": clinsig
                }))
    return out

# ---------- ClinVar E-utilities: esearch -> esummary ----------
def fetch_clinvar_by_gene_hg38(gene, api_key=None, retmax=10000):
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    common = {"db":"clinvar","retmode":"json"}
    if api_key: common["api_key"] = api_key

    # Шаг 1: ищем все VCV по гену
    esearch = _get_json(f"{base}/esearch.fcgi", {
        **common, "term": f'{gene}[gene]', "retmax": retmax
    })
    ids = esearch.get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []

    # Шаг 2: тянем summaries пакетами (до ~200 ID за раз — безопасно)
    out = []
    chunk = 200
    for i in range(0, len(ids), chunk):
        batch = ",".join(ids[i:i+chunk])
        summ = _get_json(f"{base}/esummary.fcgi", {**common, "id": batch})
        docs = summ.get("result", {})
        for vid, doc in docs.items():
            if vid == "uids": continue
            # Координаты в doc['assembly_set'][*], ищем GRCh38
            for asm in doc.get("assembly_set", []):
                if asm.get("assembly_name") in ("GRCh38", "GRCh38.p13"):
                    # малые варианты обычно в asm['position'] или в placements
                    chrom = asm.get("chr")
                    start = asm.get("start")
                    end = asm.get("stop") or asm.get("end") or start
                    ref = asm.get("reference_allele") or asm.get("ref_allele")
                    alt = asm.get("alternate_allele") or asm.get("alt_allele")
                    if chrom and start is not None:
                        out.append(_row(chrom, start, end, ref, alt, "clinvar", {
                            "vcv_id": doc.get("accession"),
                            "clinvar_significance": doc.get("clinical_significance")
                        }))
    return out

# ---------- пример использования ----------
if __name__ == "__main__":
    gene = "BRCA1"
    # 1) MyVariant (hg38)
    mv = fetch_myvariant_by_gene_hg38(gene)

    # 2) ClinVar (hg38 через esummary)
    # при желании можно добавить NCBI_API_KEY для больших выгрузок
    cv = fetch_clinvar_by_gene_hg38(gene, api_key=None)

    # Слияние и быстрая проверка
    rows = mv + cv
    print(f"{gene}: variants collected -> total {len(rows)} "
          f"(myvariant: {len(mv)}, clinvar: {len(cv)})")
    # Пример: первые 5 строк
    for r in rows[:5]:
        print(r)
