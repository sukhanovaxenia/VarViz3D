#!/bin/bash
# install.sh - Install VarViz3D dependencies

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}======================================"
echo "     VarViz3D Installation Script     "
echo "======================================${NC}"

# Check Python version
echo -e "${YELLOW}Checking Python version...${NC}"
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
REQUIRED_VERSION="3.10"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo -e "${RED}Error: Python 3.10+ required (found $PYTHON_VERSION)${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python $PYTHON_VERSION${NC}"

# Detect package manager preference
echo ""
echo "Choose installation method:"
echo "1) pip (virtual environment)"
echo "2) conda (using environment.yml)"
echo "3) Skip installation (dependencies already installed)"
read -p "Enter choice [1-3]: " CHOICE

case $CHOICE in
    1)
        echo -e "${YELLOW}Creating virtual environment...${NC}"
        python3 -m venv venviz3d
        
        # Activate virtual environment
        if [ -f "venviz3d/bin/activate" ]; then
            source venviz3d/bin/activate
        elif [ -f "venviz3d/Scripts/activate" ]; then
            source venviz3d/Scripts/activate
        fi
        
        echo -e "${YELLOW}Upgrading pip...${NC}"
        pip install --upgrade pip
        
        echo -e "${YELLOW}Installing requirements...${NC}"
        pip install -r requirements.txt
        
        echo -e "${GREEN}✓ Virtual environment created and packages installed${NC}"
        echo ""
        echo "To activate the environment, run:"
        echo "  source venviz3d/bin/activate  # Linux/Mac"
        echo "  venviz3d\\Scripts\\activate     # Windows"
        ;;
        
    2)
        echo -e "${YELLOW}Creating conda environment...${NC}"
        
        # Check if conda is installed
        if ! command -v conda &> /dev/null; then
            echo -e "${RED}Error: conda not found. Please install Miniconda or Anaconda.${NC}"
            exit 1
        fi
        
        # Create environment from yml file
        conda env create -f environment.yml
        
        echo -e "${GREEN}✓ Conda environment 'varviz3d' created${NC}"
        echo ""
        echo "To activate the environment, run:"
        echo "  conda activate varviz3d"
        ;;
        
    3)
        echo -e "${YELLOW}Skipping installation...${NC}"
        ;;
        
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

# Create necessary directories
echo -e "${YELLOW}Creating project directories...${NC}"
mkdir -p logs
mkdir -p data
mkdir -p varviz3d_ux/static/3d

# Make scripts executable
echo -e "${YELLOW}Setting script permissions...${NC}"
chmod +x start_services.sh
chmod +x stop_services.sh

# Check if viewer.html exists in the right place
if [ ! -f "varviz3d_ux/static/3d/viewer.html" ] && [ -f "varviz3d_ux/viewer.html" ]; then
    echo -e "${YELLOW}Moving viewer.html to static directory...${NC}"
    mv varviz3d_ux/viewer.html varviz3d_ux/static/3d/
fi

echo ""
echo -e "${GREEN}======================================"
echo "    Installation Complete!            "
echo "======================================${NC}"
echo ""
echo "Next steps:"
echo "1. Activate your environment (if using venv or conda)"
echo "2. Run: ./start_services.sh"
echo "3. Open: http://localhost:8501"
echo ""
echo -e "${BLUE}For help, run: ./start_services.sh --help${NC}"