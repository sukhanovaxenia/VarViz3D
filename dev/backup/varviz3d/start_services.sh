#!/bin/bash
# start_services.sh - Launch all backend services

echo "Starting Variant Visualization Services..."

# Kill any existing processes on our ports
echo "Cleaning up old processes..."
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:5001 | xargs kill -9 2>/dev/null

# Start Literature API (FastAPI on port 8000)
echo "Starting Literature API on port 8000..."
cd $(dirname "$0")
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
LIT_PID=$!

# Wait for Literature API to start
sleep 3

# Start 3D Backend (Flask on port 5001)
echo "Starting 3D Backend on port 5001..."
python backend_3d.py &
BACKEND_PID=$!

# Wait for 3D Backend to start
sleep 3

# Start Streamlit app
echo "Starting Streamlit UI on port 8501..."
streamlit run app.py &
STREAMLIT_PID=$!

echo ""
echo "==================================="
echo "All services started successfully!"
echo "==================================="
echo "Literature API: http://localhost:8000"
echo "3D Backend: http://localhost:5001"
echo "Main UI: http://localhost:8501"
echo ""
echo "Process IDs:"
echo "Literature API: $LIT_PID"
echo "3D Backend: $BACKEND_PID"
echo "Streamlit: $STREAMLIT_PID"
echo ""
echo "To stop all services, press Ctrl+C"

# Wait and handle shutdown
trap "echo 'Shutting down...'; kill $LIT_PID $BACKEND_PID $STREAMLIT_PID 2>/dev/null; exit" INT

wait