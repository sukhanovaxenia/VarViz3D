import requests

class StructureFetcher:
    UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb"
    PDB_BASE = "https://data.rcsb.org/rest/v1/core/uniprot"
    ALPHAFOLD_URL = "https://alphafold.ebi.ac.uk/entry/"

    def get_uniprot_id(self, gene_name):
        url = f"{self.UNIPROT_BASE}/search?query=gene:{gene_name}+AND+organism_id:9606&format=json&size=1"
        res = requests.get(url)
        res.raise_for_status()
        results = res.json().get('results', [])
        return results[0]['primaryAccession'] if results else None

    def get_domain_info(self, uni_id):
        url = f"{self.UNIPROT_BASE}/{uni_id}.json"
        res = requests.get(url)
        res.raise_for_status()
        features = res.json().get('features', [])
        return [
            (f['type'], f['location']['start']['value'], f['location']['end']['value'], f.get('description', ''))
            for f in features if f['type'] == 'Domain'
        ]

    def get_pdb_ids(self, uni_id):
        url = f"{self.PDB_BASE}/{uni_id}"
        res = requests.get(url)
        if res.status_code == 200:
            data = res.json()
            return data['rcsb_uniprot_container_identifiers'].get('entry_ids', [])
        return []

    def get_alphafold_url(self, uni_id):
        return f"{self.ALPHAFOLD_URL}{uni_id}"

if __name__ == "__main__":
    fetcher = StructureFetcher()
    gene = "BRCA1"
    print("UniProt ID:", fetcher.get_uniprot_id(gene))
    print("Domains:", fetcher.get_domain_info("P38398"))
    print("PDB entries:", fetcher.get_pdb_ids("P38398"))
    print("AlphaFold URL:", fetcher.get_alphafold_url("P38398"))

