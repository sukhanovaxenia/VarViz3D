from mygene import MyGeneInfo
from fastapi import APIRouter


mg = MyGeneInfo()
router = APIRouter(prefix="/api/gene", tags=["gene"])

gene = "BRCA1"  # change as needed
res = mg.query(f"symbol:{gene}", species="human", fields="summary", size=1)

if res.get("hits"):
    summary = res["hits"][0].get("summary")
    print(summary)
else:
    print(f"No summary found for {gene}")


router = APIRouter(prefix="/api/gene", tags=["gene"])

# @router.get("/info")
# def get_gene_info():
#     return {"message": "Gene info route works!"}