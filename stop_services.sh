#!/bin/bash
# stop_services.sh - Stop all VarViz3D services

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$PROJECT_DIR/.varviz3d.pids"

echo -e "${YELLOW}Stopping VarViz3D services...${NC}"

# Method 1: Use PID file if exists
if [ -f "$PID_FILE" ]; then
    echo "Using PID file to stop services..."
    PIDS=$(cat "$PID_FILE")
    for PID in $PIDS; do
        if kill -0 $PID 2>/dev/null; then
            kill $PID
            echo -e "${GREEN}✓ Stopped process $PID${NC}"
        fi
    done
    rm -f "$PID_FILE"
fi

# Method 2: Find and kill by port
echo "Checking for remaining processes on ports..."

# Kill processes on specific ports
for PORT in 8000 5001 8501; do
    PIDS=$(lsof -ti:$PORT 2>/dev/null)
    if [ -n "$PIDS" ]; then
        echo -e "${YELLOW}Stopping processes on port $PORT...${NC}"
        echo "$PIDS" | xargs kill -9 2>/dev/null
        echo -e "${GREEN}✓ Stopped processes on port $PORT${NC}"
    fi
done

# Method 3: Kill by process name pattern
echo "Checking for remaining Python processes..."
pkill -f "uvicorn main:app" 2>/dev/null
pkill -f "backend_3d.py" 2>/dev/null
pkill -f "streamlit run app.py" 2>/dev/null

echo -e "${GREEN}All VarViz3D services stopped.${NC}"