#!/bin/bash

source "$(dirname "$0")/check_curl_response.sh"

# Vérifier le nombre d'arguments
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <user_id> <vm_name>"
    exit 1
fi

# Récupérer les arguments
USER_ID=$1
VM_NAME=$2

# Définir les chemins
VM_DIR="/opt/firecracker/vm/${USER_ID}/${VM_NAME}"
SOCKET_PATH="/tmp/firecracker-sockets/${USER_ID}_${VM_NAME}.socket"
LOG_PATH="/opt/firecracker/logs/firecracker-${USER_ID}_${VM_NAME}.log"
VM_PID="/opt/firecracker/logs/firecracker-${USER_ID}_${VM_NAME}.pid"

# Vérifier si la VM existe
if [ ! -d "${VM_DIR}" ]; then
    echo "{\"status\": \"not_found\"}"
    exit 0
fi

# Vérifier si la VM est en cours d'exécution
if [ -S "${SOCKET_PATH}" ]; then
    # Vérifier si le processus Firecracker est en cours d'exécution
    pid_file="${VM_PID}"
    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null; then
            # Obtenir la configuration de la machine
            # Ajouter un timeout et vérifier le contenu
            machine_config=$(curl --unix-socket "${SOCKET_PATH}" -s --max-time 5 \
              -X GET 'http://localhost/machine-config' \
              -H 'Accept: application/json')

            if [ $? -eq 0 ] && [ -n "$machine_config" ] && echo "$machine_config" | jq . >/dev/null 2>&1; then
                echo "{\"status\": \"running\", \"machine_config\": ${machine_config}}"
            else
                echo "{\"status\": \"error\", \"message\": \"Failed to get VM status\"}"
            fi
        fi
    fi
    # Si on arrive ici, c'est que la VM n'est pas vraiment en cours d'exécution
    echo "{\"status\": \"stopped\"}"
else
    echo "{\"status\": \"stopped\"}"
fi
