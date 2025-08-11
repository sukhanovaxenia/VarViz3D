#!/bin/bash
# start_services.sh - Launch all VarViz3D backend services
# Usage: ./start_services.sh [options]
# Options:
#   -d, --dir PATH       Project directory (default: current directory)
#   -p, --port PORT      Base port (default: 8000, will use 8000, 5001, 8501)
#   -e, --env ENV        Python environment to activate (optional)
#   -h, --help           Show this help message

# Default values
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_PORT=8000
PYTHON_ENV=""
KILL_EXISTING=true

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--dir)
            PROJECT_DIR="$2"
            shift 2
            ;;
        -p|--port)
            BASE_PORT="$2"
            shift 2
            ;;
        -e|--env)
            PYTHON_ENV="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  -d, --dir PATH       Project directory (default: current directory)"
            echo "  -p, --port PORT      Base port (default: 8000)"
            echo "  -e, --env ENV        Python environment to activate"
            echo "  -h, --help           Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Calculate ports
LIT_PORT=$BASE_PORT
BACKEND_PORT=$((BASE_PORT + 1001))  # 5001 if base is 8000
STREAMLIT_PORT=$((BASE_PORT + 501))  # 8501 if base is 8000

echo -e "${GREEN}==================================="
echo "Starting VarViz3D Services"
echo "===================================${NC}"
echo "Project directory: $PROJECT_DIR"
echo "Ports: Literature API=$LIT_PORT, 3D Backend=$BACKEND_PORT, Streamlit=$STREAMLIT_PORT"

# Navigate to project directory
cd "$PROJECT_DIR" || exit 1

# Activate Python environment if specified
if [ -n "$PYTHON_ENV" ]; then
    echo -e "${YELLOW}Activating Python environment: $PYTHON_ENV${NC}"
    if [ -f "$PYTHON_ENV/bin/activate" ]; then
        source "$PYTHON_ENV/bin/activate"
    elif [ -f "$PYTHON_ENV/Scripts/activate" ]; then
        source "$PYTHON_ENV/Scripts/activate"
    else
        echo -e "${RED}Error: Cannot find Python environment at $PYTHON_ENV${NC}"
        exit 1
    fi
fi

# Check for required Python packages
echo -e "${YELLOW}Checking dependencies...${NC}"
python -c "import streamlit" 2>/dev/null || { echo -e "${RED}Error: streamlit not installed${NC}"; exit 1; }
python -c "import flask" 2>/dev/null || { echo -e "${RED}Error: flask not installed${NC}"; exit 1; }
python -c "import fastapi" 2>/dev/null || { echo -e "${RED}Error: fastapi not installed${NC}"; exit 1; }

# Kill any existing processes on our ports
if [ "$KILL_EXISTING" = true ]; then
    echo -e "${YELLOW}Cleaning up old processes...${NC}"
    lsof -ti:$LIT_PORT 2>/dev/null | xargs kill -9 2>/dev/null
    lsof -ti:$BACKEND_PORT 2>/dev/null | xargs kill -9 2>/dev/null
    lsof -ti:$STREAMLIT_PORT 2>/dev/null | xargs kill -9 2>/dev/null
    sleep 2
fi

# Create log directory
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

# Start Literature API (FastAPI on port 8000)
echo -e "${YELLOW}Starting Literature API on port $LIT_PORT...${NC}"
cd "$PROJECT_DIR/varviz3d_ux/app" || exit 1
nohup uvicorn main:app --host 0.0.0.0 --port $LIT_PORT --reload > "$LOG_DIR/literature_api.log" 2>&1 &
LIT_PID=$!

# Wait and check if Literature API started
sleep 3
if kill -0 $LIT_PID 2>/dev/null; then
    echo -e "${GREEN}✓ Literature API started (PID: $LIT_PID)${NC}"
else
    echo -e "${RED}✗ Failed to start Literature API${NC}"
    exit 1
fi

# Start 3D Backend (Flask on port 5001)
echo -e "${YELLOW}Starting 3D Backend on port $BACKEND_PORT...${NC}"
cd "$PROJECT_DIR/varviz3d_ux" || exit 1
nohup python backend_3d.py > "$LOG_DIR/backend_3d.log" 2>&1 &
BACKEND_PID=$!

# Wait and check if 3D Backend started
sleep 3
if kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "${GREEN}✓ 3D Backend started (PID: $BACKEND_PID)${NC}"
else
    echo -e "${RED}✗ Failed to start 3D Backend${NC}"
    kill $LIT_PID 2>/dev/null
    exit 1
fi

# Start Streamlit app
echo -e "${YELLOW}Starting Streamlit UI on port $STREAMLIT_PORT...${NC}"
cd "$PROJECT_DIR/varviz3d_ux" || exit 1
nohup streamlit run app.py --server.port $STREAMLIT_PORT --server.address 0.0.0.0 > "$LOG_DIR/streamlit.log" 2>&1 &
STREAMLIT_PID=$!

# Wait and check if Streamlit started
sleep 5
if kill -0 $STREAMLIT_PID 2>/dev/null; then
    echo -e "${GREEN}✓ Streamlit UI started (PID: $STREAMLIT_PID)${NC}"
else
    echo -e "${RED}✗ Failed to start Streamlit${NC}"
    kill $LIT_PID $BACKEND_PID 2>/dev/null
    exit 1
fi

# Create PID file for easy shutdown
echo "$LIT_PID $BACKEND_PID $STREAMLIT_PID" > "$PROJECT_DIR/.varviz3d.pids"

echo ""
echo -e "${GREEN}==================================="
echo "All services started successfully!"
echo "===================================${NC}"
echo -e "${GREEN}Literature API:${NC} http://localhost:$LIT_PORT"
echo -e "${GREEN}3D Backend:${NC} http://localhost:$BACKEND_PORT"
echo -e "${GREEN}Main UI:${NC} http://localhost:$STREAMLIT_PORT"
echo ""
echo "Logs are available in: $LOG_DIR/"
echo ""
echo -e "${YELLOW}To stop all services:${NC}"
echo "  - Press Ctrl+C (if running in foreground)"
echo "  - Or run: ./stop_services.sh"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down services...${NC}"
    kill $LIT_PID $BACKEND_PID $STREAMLIT_PID 2>/dev/null
    rm -f "$PROJECT_DIR/.varviz3d.pids"
    echo -e "${GREEN}Services stopped.${NC}"
    exit 0
}

# Set trap for cleanup
trap cleanup INT TERM

# Keep script running if in foreground mode
if [ -t 0 ]; then
    echo "Running in foreground mode. Press Ctrl+C to stop all services."
    while true; do
        # Check if all processes are still running
        if ! kill -0 $LIT_PID 2>/dev/null || ! kill -0 $BACKEND_PID 2>/dev/null || ! kill -0 $STREAMLIT_PID 2>/dev/null; then
            echo -e "${RED}One or more services have stopped unexpectedly.${NC}"
            cleanup
        fi
        sleep 5
    done
else
    echo "Services started in background mode."
fi