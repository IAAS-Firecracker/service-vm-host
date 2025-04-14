#!/bin/bash

source "$(dirname "$0")/check_curl_response.sh"

# Vérifier le nombre d'arguments
if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <user_id> <vm_name> <tap_device>"
    exit 1
fi

# Récupérer les arguments
USER_ID=$1
VM_NAME=$2
TAP_DEVICE=$3

# Définir les chemins
SOCKET_PATH="/tmp/firecracker-sockets/${USER_ID}_${VM_NAME}.socket"
LOG_PATH="/opt/firecracker/logs/firecracker-${USER_ID}_${VM_NAME}.log"
PID_FILE="/opt/firecracker/logs/firecracker-${USER_ID}_${VM_NAME}.pid"


# Fonction de nettoyage
cleanup() {
    local exit_code=$?
    echo "Nettoyage des ressources..."

    # 1. Supprimer le socket s'il existe
    if [ -S "${SOCKET_PATH}" ]; then
        rm -f "${SOCKET_PATH}"
        echo "Socket supprimé: ${SOCKET_PATH}"
    fi

    # 2. Arrêter le processus Firecracker
    if [ -f "${PID_FILE}" ]; then
        local pid=$(cat "${PID_FILE}")
        if ps -p "${pid}" > /dev/null; then
            kill "${pid}" 2>/dev/null || true
            echo "Processus Firecracker arrêté (PID: ${pid})"
        fi
        rm -f "${PID_FILE}"
        echo "Fichier PID supprimé: ${PID_FILE}"
    fi

    # 3. Supprimer l'interface réseau tap
    if ip link show "${TAP_DEVICE}" &>/dev/null; then
        ip link set "${TAP_DEVICE}" down
        ip link delete "${TAP_DEVICE}" type tap
        echo "Interface réseau supprimée: ${TAP_DEVICE}"
    fi

    exit ${exit_code}
}

# Enregistrer la fonction de nettoyage pour être exécutée à la sortie
trap cleanup EXIT

#Suppression de l'interface reseaux
sudo ip link del "$TAP_DEVICE"

# Vérifier si la VM est en cours d'exécution
if [ ! -S "${SOCKET_PATH}" ]; then
    echo "La VM n'est pas en cours d'exécution"
    exit 0
fi

# Envoyer la commande d'arrêt à la VM
echo "Envoi de la commande d'arrêt..."
response=$(curl --unix-socket "${SOCKET_PATH}" -i \
  -X PUT 'http://localhost/actions' \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
    "action_type": "SendCtrlAltDel"
  }')

# Vérifier la réponse
if ! check_curl_response "$response" "Stopping VM" ${LINENO} "$LOG_PATH"; then
    echo "Échec de l'arrêt gracieux, tentative d'arrêt forcé..."
    response=$(curl --unix-socket "${SOCKET_PATH}" -i \
      -X PUT 'http://localhost/actions' \
      -H 'Accept: application/json' \
      -H 'Content-Type: application/json' \
      -d '{
        "action_type": "InstanceHalt"
      }')
fi

# Attendre que le processus se termine
if [ -f "${PID_FILE}" ]; then
    pid=$(cat "${PID_FILE}")
    echo "Attente de l'arrêt du processus (PID: ${pid})..."
    for i in {1..30}; do
        if ! ps -p "${pid}" > /dev/null; then
            break
        fi
        sleep 1
    done
fi

echo "Arrêt de la VM terminé"
