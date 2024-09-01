#!/bin/bash

# Change to the hosebeast directory
cd $HOME/dev/hosebeast

# Activate the virtual environment
source .venv/bin/activate

# Check if a tmux session named "hosebeast" already exists
if tmux has-session -t hosebeast 2>/dev/null; then
    echo "Hosebeast is already running in a tmux session. Attaching..."
    tmux attach -t hosebeast
else
    # Create a new tmux session named "hosebeast", start the application, and attach to it
    echo "Starting Hosebeast in a new tmux session..."
    tmux new-session -s hosebeast "reflex run --env prod"
fi

# Note: The script will end here when the tmux session is detached
echo "Detached from Hosebeast tmux session."
echo "To reattach, use: tmux attach -t hosebeast"
echo "To detach from the session, press Ctrl+B, then D"