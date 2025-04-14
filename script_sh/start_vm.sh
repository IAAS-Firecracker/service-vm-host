#!/bin/bash

source "$(dirname "$0")/check_curl_response.sh"

# Vérifier le nombre d'arguments
if [ "$#" -ne 10 ]; then
    echo "Usage: $0 <user_id> <vm_name> <os_type> <cpu_count> <memory_size_mib> <disk_size_gb> <tap_device> <tap_ip> <vm_ip> <vm_mac>"
    exit 1
fi

# Récupérer les arguments
USER_ID=$1
VM_NAME=$2
OS_TYPE=$3
VCPU_COUNT=$4
MEM_SIZE_MIB=$5
DISK_SIZE_GB=$6
TAP_DEVICE=$7
TAP_IP=$8
VM_IP=$9
VM_MAC=${10}

# Définir les chemins
VM_DIR="/opt/firecracker/vm/${USER_ID}/${VM_NAME}"
SOCKET_PATH="/tmp/firecracker-sockets/${USER_ID}_${VM_NAME}.socket"
LOG_PATH="/opt/firecracker/logs/firecracker-${USER_ID}_${VM_NAME}.log"
KERNEL_PATH="${VM_DIR}/vmlinux-5.10.225"
CUSTOM_VM="${VM_DIR}/${OS_TYPE}.ext4"

MASK_SHORT="/30"
FC_MAC="${VM_MAC}"
# IFACE_ID="${TAP_DEVICE}"
IFACE_ID="eth0"

# Vérifier que la VM existe
if [ ! -d "${VM_DIR}" ]; then
    echo "Error: VM directory not found at ${VM_DIR}"
    exit 1
fi

# Configuration du kernel
response=$(curl --unix-socket "${SOCKET_PATH}" -i \
  -X PUT 'http://localhost/boot-source' \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -d "{
    \"kernel_image_path\": \"${KERNEL_PATH}\",
    \"boot_args\": \"console=ttyS0 reboot=k panic=1 pci=off ip=${VM_IP}::${TAP_IP}:255.255.255.252::${IFACE_ID}:off\"
  }")

check_curl_response "$response" "Configuring kernel" ${LINENO} "$LOG_PATH" || {
    get_last_error "$LOG_PATH"
    exit 1
}

# Configuration de la machine
response=$(curl --unix-socket "${SOCKET_PATH}" -i \
  -X PUT 'http://localhost/machine-config' \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -d "{
    \"vcpu_count\": ${VCPU_COUNT},
    \"mem_size_mib\": ${MEM_SIZE_MIB},
    \"track_dirty_pages\": true
  }")

check_curl_response "$response" "Configuring machine" ${LINENO} "$LOG_PATH" || {
    get_last_error "$LOG_PATH"
    exit 1
}

# Configuration du rootfs
response=$(curl --unix-socket "${SOCKET_PATH}" -i \
  -X PUT 'http://localhost/drives/rootfs' \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -d "{
    \"drive_id\": \"rootfs\",
    \"path_on_host\": \"${CUSTOM_VM}\",
    \"is_root_device\": true,
    \"is_read_only\": false
  }")

check_curl_response "$response" "Configuring rootfs" ${LINENO} "$LOG_PATH" || {
    get_last_error "$LOG_PATH"
    exit 1
}

# Journaliser la configuration réseau
echo "$(date '+%Y-%m-%d %H:%M:%S,%3N') - setting_vm_image.sh - INFO - Configuring network: TAP=${TAP_DEVICE}, TAP_IP=${TAP_IP}, VM_IP=${VM_IP}, MAC=${FC_MAC}" >> "$LOG_PATH"

# Supprimer l'ancien TAP s'il existe
sudo ip link del "$TAP_DEVICE" 2> /dev/null || true
echo "$(date '+%Y-%m-%d %H:%M:%S,%3N') - start_vm.sh - INFO - Cleaned up old TAP device: ${TAP_DEVICE}" >> "$LOG_PATH"

# Créer et configurer le TAP device
sudo ip tuntap add "$TAP_DEVICE" mode tap
sudo ip addr add "${TAP_IP}${MASK_SHORT}" dev "$TAP_DEVICE"
sudo ip link set "$TAP_DEVICE" up
echo "$(date '+%Y-%m-%d %H:%M:%S,%3N') - start_vm.sh - INFO - Created and configured TAP device: $TAP_DEVICE" >> "$LOG_PATH"

HOST_IFACE=$(ip -j route list default |jq -r '.[0].dev')
# Configurer le routage et NAT
sudo sysctl -w net.ipv4.ip_forward=1
sudo iptables -P FORWARD ACCEPT
sudo iptables -t nat -D POSTROUTING -o "$HOST_IFACE" -j MASQUERADE || true
sudo iptables -t nat -A POSTROUTING -o "$HOST_IFACE" -j MASQUERADE
sudo iptables -A FORWARD -i "$TAP_DEVICE" -o "$HOST_IFACE" -j ACCEPT
sudo iptables -A FORWARD -o "$TAP_DEVICE" -i "$HOST_IFACE" -j ACCEPT

# Sauvegarder les règles iptables
sudo sh -c "iptables-save > /etc/iptables/rules.v4"
echo "$(date '+%Y-%m-%d %H:%M:%S,%3N') - start_vm.sh - INFO - Configured routing and NAT for $TAP_DEVICE" >> "$LOG_PATH"

# This tries to determine the name of the host network interface to forward
# VM's outbound network traffic through. If outbound traffic doesn't work,
# double check this returns the correct interface!


# Configuration du réseau
network_config="{
  \"iface_id\": \"${IFACE_ID}\",
  \"guest_mac\": \"${FC_MAC}\",
  \"host_dev_name\": \"${TAP_DEVICE}\"
}"
response=$(curl --unix-socket "${SOCKET_PATH}" -i \
  -X PUT "http://localhost/network-interfaces/${IFACE_ID}" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d "${network_config}")

check_curl_response "$response" "Configuring network interface" ${LINENO} "$LOG_PATH" || {
    get_last_error "$LOG_PATH"
    exit 1
}

# Configuration du balloon
response=$(curl --unix-socket "${SOCKET_PATH}" -i \
  -X PUT 'http://localhost/balloon' \
  -H 'Content-Type: application/json' \
  -d '{
    "amount_mib": 512,
    "deflate_on_oom": true,
    "stats_polling_interval_s": 1
  }')

check_curl_response "$response" "Configuring balloon" ${LINENO} "$LOG_PATH" || {
    get_last_error "$LOG_PATH"
    exit 1
}

# Démarrer la machine
response=$(curl --unix-socket "${SOCKET_PATH}" -i \
  -X PUT 'http://localhost/actions' \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
    "action_type": "InstanceStart"
  }')

check_curl_response "$response" "Starting VM" ${LINENO} "$LOG_PATH" || {
    get_last_error "$LOG_PATH"
    exit 1
}

echo "VM started successfully"