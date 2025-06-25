#!/bin/bash

source "$(dirname "$0")/check_curl_response.sh"

# Vérifier le nombre d'arguments
if [ "$#" -ne 11 ]; then
    echo "Usage: $0 <os_type> <user_id> <ssh_public_key> <disk_size_gb> <vm_name> <vcpu_count> <mem_size_mib> <tap_device> <tap_ip> <vm_ip> <vm_mac>"
    exit 1
fi

# Récupérer les arguments
OS_TYPE=$1
USER_ID=$2
SSH_PUBLIC_KEY=$3
DISK_SIZE_GB=$4
VM_NAME=$5
VCPU_COUNT=$6
MEM_SIZE_MIB=$7
TAP_DEVICE=$8
TAP_IP=$9
VM_IP=${10}
VM_MAC=${11}

# Définir les chemins
BASE_DIR="/opt/firecracker"
VM_DIR="${BASE_DIR}/vm/${USER_ID}/${VM_NAME}"
SOCKET_PATH="/tmp/firecracker-sockets/${USER_ID}_${VM_NAME}.socket"
CUSTOM_VM="${VM_DIR}/${OS_TYPE}.ext4"
KERNEL_PATH="${VM_DIR}/vmlinux-5.10.225"
LOG_PATH="${BASE_DIR}/logs/firecracker-${USER_ID}_${VM_NAME}.log"

# Créer le répertoire de logs s'il n'existe pas
sudo mkdir -p "$(dirname "$LOG_PATH")"
sudo chmod 777 "$(dirname "$LOG_PATH")"

# Vérifier que les fichiers nécessaires existent
if [ ! -f "${KERNEL_PATH}" ]; then
    echo "Error: Kernel file not found at ${KERNEL_PATH}"
    exit 1
fi

if [ ! -f "${CUSTOM_VM}" ]; then
    echo "Error: Custom VM image not found at ${CUSTOM_VM}"
    exit 1
fi

# Configurer le réseau
TAP_DEV="${TAP_DEVICE}"
TAP_IP="${TAP_IP}"
VM_IP="${VM_IP}"
MASK_SHORT="/30"
FC_MAC="${VM_MAC}"
IFACE_ID="${TAP_DEV}"

# Journaliser la configuration réseau
echo "$(date '+%Y-%m-%d %H:%M:%S,%3N') - setting_vm_image.sh - INFO - Configuring network: TAP=${TAP_DEV}, TAP_IP=${TAP_IP}, VM_IP=${VM_IP}, MAC=${FC_MAC}" >> "$LOG_PATH"

# Supprimer l'ancien TAP s'il existe
sudo ip link del "$TAP_DEV" 2> /dev/null || true
echo "$(date '+%Y-%m-%d %H:%M:%S,%3N') - setting_vm_image.sh - INFO - Cleaned up old TAP device: ${TAP_DEV}" >> "$LOG_PATH"

# Créer un nouveau TAP
sudo ip tuntap add dev "$TAP_DEV" mode tap
echo "$(date '+%Y-%m-%d %H:%M:%S,%3N') - setting_vm_image.sh - INFO - Created new TAP device: ${TAP_DEV}" >> "$LOG_PATH"

# Configurer le TAP
sudo ip addr add "${TAP_IP}${MASK_SHORT}" dev "$TAP_DEV"
sudo ip link set dev "$TAP_DEV" up
echo "$(date '+%Y-%m-%d %H:%M:%S,%3N') - setting_vm_image.sh - INFO - Configured TAP device with IP: ${TAP_IP}" >> "$LOG_PATH"

# Activer le forwarding
sudo sh -c "echo 1 > /proc/sys/net/ipv4/ip_forward"
echo "$(date '+%Y-%m-%d %H:%M:%S,%3N') - setting_vm_image.sh - INFO - Enabled IP forwarding" >> "$LOG_PATH"

HOST_IFACE=$(ip -j route list default |jq -r '.[0].dev')

# Configurer iptables pour le NAT
sudo iptables -P FORWARD ACCEPT
sudo iptables -t nat -D POSTROUTING -o "$HOST_IFACE" -j MASQUERADE || true
sudo iptables -t nat -A POSTROUTING -o "$HOST_IFACE" -j MASQUERADE
echo "$(date '+%Y-%m-%d %H:%M:%S,%3N') - setting_vm_image.sh - INFO - Configured iptables NAT rules $HOST_IFACE" >> "$LOG_PATH"

# Setup internet access in the guest
sudo ip route add default via "$TAP_IP" dev ${TAP_DEV}

# Setup DNS resolution in the guest
sudo echo 'nameserver 8.8.8.8' > /etc/resolv.conf

# Configuration de la VM via l'API Firecracker
response=$(curl --unix-socket "${SOCKET_PATH}" -i \
  -X PUT 'http://localhost/machine-config' \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -d "{
    \"vcpu_count\": ${VCPU_COUNT},
    \"mem_size_mib\": ${MEM_SIZE_MIB},
    \"smt\": false
  }")

check_curl_response "$response" "Configuring VM machine config" ${LINENO} "$LOG_PATH" || {
    get_last_error "$LOG_PATH"
    exit 1
}

echo "$(date '+%Y-%m-%d %H:%M:%S,%3N') - setting_vm_image.sh - INFO - Configured VM machine config" >> "$LOG_PATH"

# Configuration du kernel
response=$(curl --unix-socket "${SOCKET_PATH}" -i \
  -X PUT 'http://localhost/boot-source' \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -d "{
    \"kernel_image_path\": \"${KERNEL_PATH}\",
    \"boot_args\": \"console=ttyS0 reboot=k panic=1 pci=off\"
  }")

check_curl_response "$response" "Configuring kernel" ${LINENO} "$LOG_PATH" || {
    get_last_error "$LOG_PATH"
    exit 1
}

echo "$(date '+%Y-%m-%d %H:%M:%S,%3N') - setting_vm_image.sh - INFO - Configured kernel" >> "$LOG_PATH"

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

echo "$(date '+%Y-%m-%d %H:%M:%S,%3N') - setting_vm_image.sh - INFO - Configured rootfs" >> "$LOG_PATH"

# Configuration du réseau
network_config="{
  \"iface_id\": \"${IFACE_ID}\",
  \"guest_mac\": \"${FC_MAC}\",
  \"host_dev_name\": \"${TAP_DEV}\"
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

echo "$(date '+%Y-%m-%d %H:%M:%S,%3N') - setting_vm_image.sh - INFO - Configured network interface" >> "$LOG_PATH"

# Configuration du disque
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

echo "$(date '+%Y-%m-%d %H:%M:%S,%3N') - setting_vm_image.sh - INFO - Configured balloon" >> "$LOG_PATH"

# Configurer le réseau dans l'image
MOUNT_DIR="/mnt/vm_${VM_NAME}"
sudo mkdir -p "$MOUNT_DIR"
sudo mount -o loop "$CUSTOM_VM" "$MOUNT_DIR"

# Créer le fichier de configuration réseau
cat > /tmp/01-netcfg.yaml << EOF
network:
  version: 2
  renderer: networkd
  ethernets:
    ${IFACE_ID}:
      addresses: ["${VM_IP}${MASK_SHORT}"]
      routes:
        - to: default
          via: ${TAP_IP}
      nameservers:
        addresses: [8.8.8.8, 1.1.1.1]
      dhcp4: false
      dhcp6: false
      optional: false
EOF

# Copier la configuration réseau dans l'image
sudo mkdir -p "$MOUNT_DIR/etc/netplan"
sudo cp /tmp/01-netcfg.yaml "$MOUNT_DIR/etc/netplan/"

# Configurer le fichier resolv.conf
cat > /tmp/resolv.conf << EOF
nameserver 8.8.8.8
nameserver 1.1.1.1
EOF

sudo cp /tmp/resolv.conf "$MOUNT_DIR/etc/resolv.conf"

# Configurer le hostname
echo "${VM_NAME}" | sudo tee "$MOUNT_DIR/etc/hostname"

# Configurer le fichier hosts
echo -e "127.0.0.1\tlocalhost\n${VM_IP%/*}\t${VM_NAME}" | sudo tee "$MOUNT_DIR/etc/hosts"

# Activer le démarrage automatique de l'interface réseau
sudo chroot "$MOUNT_DIR" /bin/bash -c "systemctl enable systemd-networkd"
sudo chroot "$MOUNT_DIR" /bin/bash -c "systemctl enable systemd-resolved"

# Désactiver le service cloud-init s'il existe
if [ -f "$MOUNT_DIR/etc/cloud/cloud.cfg" ]; then
    sudo sed -i 's/^network: {config: disabled}/network: {config: true}/' "$MOUNT_DIR/etc/cloud/cloud.cfg"
fi

# Appliquer la configuration réseau
echo "Applying network configuration..."
sudo chroot "$MOUNT_DIR" netplan generate
sudo chroot "$MOUNT_DIR" netplan apply

# Nettoyer et démonter
sync
echo "$(date '+%Y-%m-%d %H:%M:%S,%3N') - setting_vm_image.sh - INFO - Configured network settings in guest OS" >> "$LOG_PATH"
sudo umount -l "$MOUNT_DIR"
sudo rmdir "$MOUNT_DIR"

echo "VM configuration completed successfully"