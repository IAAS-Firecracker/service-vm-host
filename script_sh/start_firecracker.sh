#!/bin/bash

# Usage: ./start_firecracker.sh <user_id> <vm_name>
USER_ID=$1
VM_NAME=$2

if [ -z "$USER_ID" ] || [ -z "$VM_NAME" ]; then
    echo "Usage: $0 <user_id> <vm_name>"
    exit 1
fi

# Créer le dossier pour les sockets et les logs
SOCKET_DIR="/tmp/firecracker-sockets"
LOG_DIR="/opt/firecracker/logs"
mkdir -p "$SOCKET_DIR" "$LOG_DIR"
chmod 777 "$SOCKET_DIR" "$LOG_DIR"

# Définir les chemins
SOCKET_PATH="${SOCKET_DIR}/${USER_ID}_${VM_NAME}.socket"
LOG_FILE="${LOG_DIR}/firecracker-${USER_ID}_${VM_NAME}.log"
PID_FILE="${LOG_DIR}/firecracker-${USER_ID}_${VM_NAME}.pid"

# Supprimer les anciens fichiers s'ils existent
rm -f "$SOCKET_PATH"
rm -f "$PID_FILE"

# Démarrer Firecracker en arrière-plan
nohup firecracker \
    --api-sock "$SOCKET_PATH" \
    > "$LOG_FILE" 2>&1 & 

# Sauvegarder le PID
echo $! > "$PID_FILE"

# Attendre que le socket soit créé
MAX_WAIT=30
WAIT_COUNT=0
while [ ! -S "$SOCKET_PATH" ] && [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    sleep 0.1
    WAIT_COUNT=$((WAIT_COUNT + 1))
done

if [ ! -S "$SOCKET_PATH" ]; then
    echo "Error: Socket not created after ${MAX_WAIT} seconds"
    exit 1
fi

echo "Firecracker started successfully with PID $(cat "$PID_FILE")"
