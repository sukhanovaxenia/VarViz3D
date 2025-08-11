#!/bin/bash
# Complete setup script for VarViz3D

echo "🧬 Setting up VarViz3D..."

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check prerequisites
check_requirements() {
    echo "Checking requirements..."
    
    # Check Node.js
    if ! command -v node &> /dev/null; then
        echo -e "${RED}❌ Node.js is not installed${NC}"
        exit 1
    fi
    
    # Check npm
    if ! command -v npm &> /dev/null; then
        echo -e "${RED}❌ npm is not installed${NC}"
        exit 1
    fi
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python 3 is not installed${NC}"
        exit 1
    fi
    
    # Check Docker (optional)
    if command -v docker &> /dev/null; then
        echo -e "${GREEN}✅ Docker found${NC}"
        USE_DOCKER=true
    else
        echo -e "${YELLOW}⚠️  Docker not found - will use local setup${NC}"
        USE_DOCKER=false
    fi
}

# Setup backend
setup_backend() {
    echo -e "\n${YELLOW}Setting up backend...${NC}"
    
    cd backend || exit
    
    # Create virtual environment
    python3 -m venv venv
    source venv/bin/activate
    
    # Install dependencies
    pip install --upgrade pip
    pip install -r requirements.txt
    
    # Download SpaCy model
    python -m spacy download en_core_sci_sm
    
    # Create .env file if not exists
    if [ ! -f .env ]; then
        cp .env.example .env
        echo -e "${GREEN}✅ Created backend .env file${NC}"
    fi
    
    cd ..
}

# Setup frontend
setup_frontend() {
    echo -e "\n${YELLOW}Setting up frontend...${NC}"
    
    cd frontend || exit
    
    # Install dependencies
    npm install
    
    # Create .env.local file if not exists
    if [ ! -f .env.local ]; then
        echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
        echo -e "${GREEN}✅ Created frontend .env.local file${NC}"
    fi
    
    cd ..
}

# Setup with Docker
setup_docker() {
    echo -e "\n${YELLOW}Setting up with Docker...${NC}"
    
    # Build images
    docker-compose build
    
    # Start services
    docker-compose up -d
    
    echo -e "${GREEN}✅ Docker services started${NC}"
}

# Main setup flow
main() {
    check_requirements
    
    if [ "$USE_DOCKER" = true ]; then
        setup_docker
    else
        setup_backend
        setup_frontend
    fi
    
    echo -e "\n${GREEN}🎉 Setup complete!${NC}"
    echo -e "\nTo start the application:"
    
    if [ "$USE_DOCKER" = true ]; then
        echo "  docker-compose up"
    else
        echo "  Backend: cd backend && source venv/bin/activate && uvicorn app.main:app --reload"
        echo "  Frontend: cd frontend && npm run dev"
    fi
    
    echo -e "\nAccess the application at:"
    echo "  Frontend: http://localhost:3000"
    echo "  Backend API: http://localhost:8000/docs"
}

# Run main
main
