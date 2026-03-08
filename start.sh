#!/bin/bash
set -e

cleanup() {
    echo ""
    echo "Shutting down..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
    echo "Done."
}
trap cleanup EXIT INT TERM

echo "=== CrowdLens ==="

# Start backend
echo "Starting backend on :8000..."
cd backend
source .venv/bin/activate
DATABASE_PATH=../data/monitor.db VIDEOS_DIR=../videos python main.py &
BACKEND_PID=$!
cd ..

# Start frontend
echo "Starting frontend on :5173..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo "Press Ctrl+C to stop."
echo ""

wait
