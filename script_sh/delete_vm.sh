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
VM_DIR="/opt/firecracker/vm/${USER_ID}/${VM_NAME}"
SOCKET_PATH="/tmp/firecracker-sockets/${USER_ID}_${VM_NAME}.socket"
LOG_PATH="/opt/firecracker/logs/firecracker-${USER_ID}_${VM_NAME}.log"
PID_FILE="/opt/firecracker/logs/firecracker-${USER_ID}_${VM_NAME}.pid"

ROOTFS_PATH="${VM_DIR}/rootfs.ext4"
KERNEL_PATH="${VM_DIR}/vmlinux"

# Vérifier si la VM existe
if [ ! -d "${VM_DIR}" ]; then
    echo "La VM n'existe pas"
    exit 0
fi

# Fonction pour arrêter la VM si elle est en cours d'exécution
stop_vm() {
    if [ -S "${SOCKET_PATH}" ] && [ -f "${PID_FILE}" ]; then
        echo "Arrêt de la VM en cours..."
        # Appeler le script d'arrêt
        "$(dirname "$0")/stop_vm.sh" "${USER_ID}" "${VM_NAME}"
        # Attendre que la VM soit complètement arrêtée
        sleep 5
    fi
}

# Fonction pour nettoyer les ressources réseau
cleanup_network() {
    # Supprimer l'interface tap si elle existe
    if ip link show "${TAP_DEVICE}" &>/dev/null; then
        echo "Suppression de l'interface réseau ${TAP_DEVICE}..."
        ip link set "${TAP_DEVICE}" down
        ip link delete "${TAP_DEVICE}" type tap
    fi
}

# Fonction pour supprimer les fichiers
cleanup_files() {
    echo "Suppression des fichiers..."
    
    # Supprimer le socket s'il existe
    [ -S "${SOCKET_PATH}" ] && sudo rm -f "${SOCKET_PATH}"
    
    # Supprimer le fichier PID s'il existe
    [ -f "${PID_FILE}" ] && sudo rm -f "${PID_FILE}"
    
    # Supprimer le fichier de log s'il existe
    [ -f "${LOG_PATH}" ] && sudo rm -f "${LOG_PATH}"
    
    # Supprimer les fichiers de configuration s'ils existent
    [ -f "${VM_DIR}/config.json" ] && sudo rm -f "${VM_DIR}/config.json"
    [ -f "${VM_DIR}/vmlinux" ] && sudo rm -f "${VM_DIR}/vmlinux"
    [ -f "${VM_DIR}/rootfs.ext4" ] && sudo rm -f "${VM_DIR}/rootfs.ext4"
    
    # Supprimer le répertoire de la VM
    if [ -d "${VM_DIR}" ]; then
        sudo rm -rf "${VM_DIR}"
        echo "Répertoire de la VM supprimé: ${VM_DIR}"
    fi
}

# Arrêter la VM si elle est en cours d'exécution
stop_vm

# Nettoyer les ressources réseau
cleanup_network

# Supprimer tous les fichiers
cleanup_files

echo "VM supprimée avec succès"
