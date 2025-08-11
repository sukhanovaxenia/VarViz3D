#!/bin/bash
# scripts/dev.sh - Development helper script

# Start both frontend and backend in development mode
tmux new-session -d -s varviz3d
tmux send-keys -t varviz3d:0 'cd backend && source venv/bin/activate && uvicorn app.main:app --reload' C-m
tmux split-window -h -t varviz3d:0
tmux send-keys -t varviz3d:0.1 'cd frontend && npm run dev' C-m
tmux attach-session -t varviz3d