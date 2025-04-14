#!/bin/bash

# Définir les chemins
VM_BASE_DIR="/opt/firecracker/vm"
SOCKET_DIR="/tmp/firecracker-sockets"

# Vérifier que le répertoire de base existe
if [ ! -d "${VM_BASE_DIR}" ]; then
    echo "[]"
    exit 0
fi

# Fonction pour vérifier si une VM est en cours d'exécution
is_vm_running() {
    local user_id=$1
    local vm_name=$2
    local socket_path="${SOCKET_DIR}/${user_id}_${vm_name}.socket"
    if [ -S "${socket_path}" ]; then
        echo "running"
    else
        echo "stopped"
    fi
}

# Liste toutes les VMs
vm_list="["
first=true

for user_dir in "${VM_BASE_DIR}"/*; do
    if [ -d "${user_dir}" ]; then
        user_id=$(basename "${user_dir}")
        for vm_dir in "${user_dir}"/*; do
            if [ -d "${vm_dir}" ]; then
                vm_name=$(basename "${vm_dir}")
                status=$(is_vm_running "${user_id}" "${vm_name}")
                
                if [ "${first}" = true ]; then
                    first=false
                else
                    vm_list="${vm_list},"
                fi
                
                vm_list="${vm_list}{\"user_id\":\"${user_id}\",\"name\":\"${vm_name}\",\"status\":\"${status}\"}"
            fi
        done
    fi
done

vm_list="${vm_list}]"
echo "${vm_list}"
