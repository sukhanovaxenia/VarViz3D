# VarViz3D
Complete Genetic Variation Visualization Source
## 🧬 Overview
VarViz3D is a comprehensive web platform for visualizing genetic variants in both 2D protein diagrams and 3D structures. Built for the Understanding and Representing Patterns of Genetic Variation in Human Genes hackathon challenge.

## ✨ Key Features

- Multi-source Variant Annotation: Integrates ClinVar, gnomAD, MyVariant.info, and more
- 2D Protein Visualization: Interactive lollipop plots with domain annotations
- 3D Structure Mapping: Variants mapped to PDB/AlphaFold structures
- Literature Mining: NLP-powered extraction of variant mentions from PubMed
- GO Impact Analysis: Assesses variant effects on gene functions
- Real-time Analysis: WebSocket updates for long-running tasks

## 🚀 Quick Start (5 Minutes)
### Prerequisites

- Docker & Docker Compose
- Git
- 8GB RAM minimum

### One-Command Setup
```bash
# Clone and start everything
git clone https://github.com/your-team/varviz3d.git
cd varviz3d
chmod +x start.sh
./start.sh
```
**Thats it!** Access the app at:
- 🌐 **Frontend**: http://localhost:3000
- 📡 **API**: http://localhost:8000/docs

## 💻 Manual Setup (If Preferred)

### Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_sci_sm
uvicorn app.main:app --reload
```
### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
### Service Setup
```bash
# PostgreSQL
docker run -d --name postgres \
  -e POSTGRES_PASSWORD=password \
  -p 5432:5432 postgres:14

# Redis
docker run -d --name redis \
  -p 6379:6379 redis:7-alpine
```

## 📊 Demo Usage
### 1. Quick Demo Example - 
```bash

```
### 2. Upload VCF File
```bash

```

### 3. Batch Analysis
```python

```

## 🏗️ Architecture

## 🔧 Configuration
### Environment Variables
Create `.env` files:
```bash

```

### API Rate Limits

## 📚 API Documentation
### Core Endpoints
**Analyze Variants**
```http

```

**Get Protein Structure**
```http

```

**Upload VCF**
```http

```
Full API docs available at http://localhost:8000/docs

## 🎯 Hackathon Timeline

## 🚢 Deployment
### Quick Deploy to Cloud
**Vercel (Frontend)**
```bash

```

**Railway (Full Stack)**
```bash

```

**Docker Compose (VPS)**
```bash

```

## 🧪 Testing
```bash

```

## 🤝 Contributing
1. Fork the repository
2. Create feature branch (git checkout -b feature/amazing-feature)
3. Commit changes (git commit -m 'Add amazing feature')
4. Push to branch (git push origin feature/amazing-feature)
5. Open Pull Request

## 🐛 Troubleshooting

## 📞 Support

## 📄 License
