#!/bin/bash
# scripts/test-api.sh - Test API endpoints

API_URL="http://localhost:8000"

echo "Testing VarViz3D API..."

# Test health endpoint
echo -e "\n1. Testing health endpoint..."
curl -s "$API_URL/health" | jq .

# Test variant analysis
echo -e "\n2. Testing variant analysis..."
curl -s -X POST "$API_URL/api/v1/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "gene_symbol": "TP53",
    "variants": [
      {
        "chromosome": "17",
        "position": 7577120,
        "reference": "G",
        "alternate": "A"
      }
    ]
  }' | jq .

echo -e "\nAPI tests complete!"