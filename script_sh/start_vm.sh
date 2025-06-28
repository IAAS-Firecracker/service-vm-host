#!/bin/bash

source "$(dirname "$0")/check_curl_response.sh"

if [ "$#" -ne 10 ]; then
    echo "Usage: $0 <user_id> <vm_name> <os_type> <cpu_count> <memory_size_mib> <disk_size_gb> <tap_device> <tap_ip> <vm_ip> <vm_mac>"
    exit 1
fi

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

VM_DIR="/opt/firecracker/vm/${USER_ID}/${VM_NAME}"
SOCKET_PATH="/tmp/firecracker-sockets/${USER_ID}_${VM_NAME}.socket"
LOG_PATH="/opt/firecracker/logs/firecracker-${USER_ID}_${VM_NAME}.log"
KERNEL_PATH="${VM_DIR}/vmlinux-5.10.225"
CUSTOM_VM="${VM_DIR}/${OS_TYPE}.ext4"

MASK_SHORT="/30"
FC_MAC="${VM_MAC}"
IFACE_ID="eth0"

# Vérification de l'existence
if [ ! -d "${VM_DIR}" ]; then
    echo "Error: VM directory not found at ${VM_DIR}"
    exit 1
fi

# Kernel
curl --unix-socket "${SOCKET_PATH}" -i \
  -X PUT 'http://localhost/boot-source' \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -d "{
    \"kernel_image_path\": \"${KERNEL_PATH}\",
    \"boot_args\": \"console=ttyS0 reboot=k panic=1 pci=off ip=${VM_IP}::${TAP_IP}:255.255.255.252::${IFACE_ID}:off\"
  }" > /dev/null

# Machine config
curl --unix-socket "${SOCKET_PATH}" -i \
  -X PUT 'http://localhost/machine-config' \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -d "{
    \"vcpu_count\": ${VCPU_COUNT},
    \"mem_size_mib\": ${MEM_SIZE_MIB},
    \"track_dirty_pages\": true
  }" > /dev/null

# Disque rootfs
curl --unix-socket "${SOCKET_PATH}" -i \
  -X PUT 'http://localhost/drives/rootfs' \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -d "{
    \"drive_id\": \"rootfs\",
    \"path_on_host\": \"${CUSTOM_VM}\",
    \"is_root_device\": true,
    \"is_read_only\": false
  }" > /dev/null

# TAP networking
sudo ip link del "$TAP_DEVICE" 2>/dev/null || true
sudo ip tuntap add "$TAP_DEVICE" mode tap
sudo ip addr add "${TAP_IP}${MASK_SHORT}" dev "$TAP_DEVICE"
sudo ip link set "$TAP_DEVICE" up

HOST_IFACE=$(ip -j route list default | jq -r '.[0].dev')
sudo sysctl -w net.ipv4.ip_forward=1
sudo iptables -P FORWARD ACCEPT
sudo iptables -t nat -D POSTROUTING -o "$HOST_IFACE" -j MASQUERADE || true
sudo iptables -t nat -A POSTROUTING -o "$HOST_IFACE" -j MASQUERADE
sudo iptables -A FORWARD -i "$TAP_DEVICE" -o "$HOST_IFACE" -j ACCEPT
sudo iptables -A FORWARD -o "$TAP_DEVICE" -i "$HOST_IFACE" -j ACCEPT

# Option : Port forwarding pour accès SSH depuis le LAN
# Décommenter les lignes suivantes si vous voulez l'accès SSH depuis le LAN
SSH_PORT=$((2200 + ${VM_IP##*.}))  # Port SSH unique basé sur l'IP de la VM
sudo iptables -t nat -A PREROUTING -i "$HOST_IFACE" -p tcp --dport "$SSH_PORT" -j DNAT --to-destination "${VM_IP}:22"
echo "SSH access from LAN: ssh root@$(hostname -I | awk '{print $1}') -p $SSH_PORT"

sudo sh -c "iptables-save > /etc/iptables/rules.v4"

# Interface réseau FC
network_config="{
  \"iface_id\": \"${IFACE_ID}\",
  \"guest_mac\": \"${FC_MAC}\",
  \"host_dev_name\": \"${TAP_DEVICE}\"
}"
curl --unix-socket "${SOCKET_PATH}" -i \
  -X PUT "http://localhost/network-interfaces/${IFACE_ID}" \
  -H "Content-Type: application/json" \
  -d "${network_config}" > /dev/null

# Ballooning
curl --unix-socket "${SOCKET_PATH}" -i \
  -X PUT 'http://localhost/balloon' \
  -H 'Content-Type: application/json' \
  -d '{
    "amount_mib": 512,
    "deflate_on_oom": true,
    "stats_polling_interval_s": 1
  }' > /dev/null

# Lancer la VM
curl --unix-socket "${SOCKET_PATH}" -i \
  -X PUT 'http://localhost/actions' \
  -H 'Content-Type: application/json' \
  -d '{
    "action_type": "InstanceStart"
  }' > /dev/null

echo "VM started successfully"