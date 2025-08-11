# gene_to_uniprot.py
# Простая обёртка над UniProt REST API для резолва символа гена → UniProt Accession.
# Приоритет: человек (9606), reviewed (Swiss-Prot), canonical (без "-1/-2" в accession),
# затем любые reviewed, затем любые.

from __future__ import annotations
import requests
from typing import Optional, Dict, Any, List

TIMEOUT = 20
HEADERS = {"User-Agent": "VarViz3D/resolve/0.1"}
UNIPROT_SEARCH = (
    "https://rest.uniprot.org/uniprotkb/search"
    "?query=gene_exact:{sym}+AND+organism_id:{org}"
    "+AND+reviewed:true&format=json&size=25"
)

class UniProtResolver:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update(HEADERS)

    def resolve(self, symbol: str, organism: int = 9606) -> Dict[str, Any]:
        """
        Возвращает лучший UniProt Accession для символа гена.
        {
          "query": "BRCA1", "organism": 9606,
          "best": {"accession":"P38398","gene":"BRCA1","entryType":"Swiss-Prot","proteinName":"..."},
          "alternatives": [ ... ]  # до 10 штук
        }
        """
        sym = (symbol or "").strip()
        if not sym:
            return {"query": symbol, "organism": organism, "best": None, "alternatives": []}

        r = self.s.get(UNIPROT_SEARCH.format(sym=sym, org=organism), timeout=TIMEOUT)
        r.raise_for_status()
        j = r.json() or {}
        results: List[Dict[str, Any]] = j.get("results") or []

        def as_item(rec: Dict[str, Any]) -> Dict[str, Any]:
            acc = rec.get("primaryAccession")
            entry_type = rec.get("entryType")  # "Swiss-Prot" / "TrEMBL"
            ids = rec.get("uniProtkbId")  # e.g., BRCA1_HUMAN
            prot = ((rec.get("proteinDescription") or {}).get("recommendedName") or {}).get("fullName") or ""
            genes = [g.get("geneName", {}).get("value") for g in rec.get("genes", []) if g.get("geneName")]
            return {
                "accession": acc,
                "entryType": entry_type,
                "proteinName": prot,
                "uniProtkbId": ids,
                "genes": [g for g in genes if g],
            }

        items = [as_item(r) for r in results if r.get("primaryAccession")]

        if not items:
            # второй шанс: снимаем reviewed:true
            alt = self.s.get(
                UNIPROT_SEARCH.replace("+AND+reviewed:true", "").format(sym=sym, org=organism),
                timeout=TIMEOUT,
            )
            alt.raise_for_status()
            j2 = alt.json() or {}
            results2 = j2.get("results") or []
            items = [as_item(r) for r in results2 if r.get("primaryAccession")]

        if not items:
            return {"query": sym, "organism": organism, "best": None, "alternatives": []}

        # стратегия выбора «лучшего»
        # 1) Swiss-Prot и не содержит «-» (канонический)
        def score(it: Dict[str, Any]) -> tuple:
            swiss = 1 if (it.get("entryType") == "Swiss-Prot") else 0
            canonical = 1 if it.get("accession") and "-" not in it["accession"] else 0
            # точное совпадение гена в списке
            exact_gene = 1 if sym.upper() in [g.upper() for g in it.get("genes", [])] else 0
            return (swiss, canonical, exact_gene)

        items.sort(key=score, reverse=True)
        best = items[0]
        return {
            "query": sym,
            "organism": organism,
            "best": best,
            "alternatives": items[1:11],
        }