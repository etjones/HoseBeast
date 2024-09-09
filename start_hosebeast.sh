#!/bin/bash
# Function to print help message
print_help() {
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  --mock VALUE    Set mock value (default: 0)"
    echo "  --env VALUE     Set environment (dev or prod, default: dev)"
    echo "  -h, --help      Display this help message"
}

# Function to parse command line arguments
parse_arguments() {
    local mock=0
    local env="dev"

    while [[ $# -gt 0 ]]; do
        case $1 in
            --mock)
                mock="$2"
                shift 2
                ;;
            --env)
                env="$2"
                if [[ "$env" != "dev" && "$env" != "prod" ]]; then
                    echo "Error: --env must be either 'dev' or 'prod'"
                    exit 1
                fi
                shift 2
                ;;
            -h|--help)
                print_help
                exit 0
                ;;
            *)
                echo "Unknown argument: $1"
                print_help
                exit 1
                ;;
        esac
    done

    echo "$mock $env"
}

# Function to check and attach to tmux session
attach_or_start_hosebeast() {
    # Check if a tmux session named "hosebeast" already exists
    if tmux has-session -t hosebeast 2>/dev/null; then
        echo "Hosebeast is already running in a tmux session. Attaching..."
        tmux attach -t hosebeast
    else
        # Create a new tmux session named "hosebeast", start the application, and attach to it
        echo "Starting Hosebeast in a new tmux session..."
        export HOSEBEAST_MOCK=$MOCK
        tmux new-session -d -s hosebeast
        tmux send-keys -t hosebeast "uv run reflex run --env $ENV" C-m
        tmux attach -t hosebeast
    fi    
    # Note: The script will end here when the tmux session is detached
    echo "Detached from Hosebeast tmux session."
    echo "To reattach, use: tmux attach -t hosebeast"
    echo "To detach from the session, press Ctrl+B, then D"    
}

# Main function to orchestrate the script
main() {
    read -r MOCK ENV <<< $(parse_arguments "$@")
    cd $HOME/dev/hosebeast
    attach_or_start_hosebeast
}

# Call the main function with all script arguments
main "$@"
