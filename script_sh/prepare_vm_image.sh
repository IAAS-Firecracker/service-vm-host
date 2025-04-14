#!/bin/bash

# Usage: ./prepare_vm_image.sh <os_type> <user_id> <ssh_public_key> <disk_size_gb> <vm_name> <root_password>
# Example: ./prepare_vm_image.sh ubuntu-24.04 user123 "ssh-rsa AAAA..." 5 "zaz" "MySecurePass123"

OS_TYPE=$1
USER_ID=$2
SSH_PUBLIC_KEY=$3
DISK_SIZE_GB=$4
VM_NAME=$5
ROOT_PASSWORD=$6

if [ -z "$OS_TYPE" ] || [ -z "$USER_ID" ] || [ -z "$SSH_PUBLIC_KEY" ] || [ -z "$DISK_SIZE_GB" ] || [ -z "$VM_NAME" ] || [ -z "$ROOT_PASSWORD" ]; then
    echo "Usage: $0 <os_type> <user_id> <ssh_public_key> <disk_size_gb> <vm_name> <root_password>"
    exit 1
fi

ARCH="$(uname -m)"
BASE_DIR="/opt/firecracker"
VM_DIR="${BASE_DIR}/vm/${USER_ID}/${VM_NAME}"
ROOTFS_DIR="${BASE_DIR}/rootfs"

# Create directories with proper permissions
sudo mkdir -p "${VM_DIR}"
sudo chown -R $USER:$USER "${BASE_DIR}"
sudo chmod -R 777 "${BASE_DIR}"

# Download base image if not exists
BASE_SQUASHFS="${ROOTFS_DIR}/${OS_TYPE}.squashfs.upstream"
if [ ! -f "${BASE_SQUASHFS}" ]; then
    case ${OS_TYPE} in
        "ubuntu-24.04")
            wget -O "${BASE_SQUASHFS}" "https://s3.amazonaws.com/spec.ccfc.min/firecracker-ci/v1.11/${ARCH}/ubuntu-24.04.squashfs"
            ;;
        "ubuntu-22.04")
            wget -O "${BASE_SQUASHFS}" "https://s3.amazonaws.com/spec.ccfc.min/firecracker-ci/v1.11/${ARCH}/ubuntu-22.04.squashfs"
            ;;
        "alpine")
            wget -O "${BASE_SQUASHFS}" "https://s3.amazonaws.com/spec.ccfc.min/firecracker-ci/v1.11/${ARCH}/alpine.squashfs"
            ;;
        "centos")
            wget -O "${BASE_SQUASHFS}" "https://s3.amazonaws.com/spec.ccfc.min/firecracker-ci/v1.11/${ARCH}/centos.squashfs"
            ;;
        *)
            echo "Unsupported OS type: ${OS_TYPE}"
            exit 1
            ;;
    esac
fi

sudo cp "${ROOTFS_DIR}/${OS_TYPE}.squashfs.upstream" "${VM_DIR}/"
sudo cp "${BASE_DIR}/vmlinux-5.10.225" "${VM_DIR}/"


cd "${VM_DIR}"

# Extract base image
unsquashfs "${OS_TYPE}.squashfs.upstream"

# Configure SSH for the user
mkdir -p squashfs-root/root/.ssh
echo "${SSH_PUBLIC_KEY}" > squashfs-root/root/.ssh/authorized_keys

# Set root password provided by user
echo "root:${ROOT_PASSWORD}" | sudo chroot squashfs-root chpasswd

# Enable and configure SSH
sudo chroot squashfs-root systemctl enable ssh
sudo chroot squashfs-root sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
sudo chroot squashfs-root sed -i 's/#PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config
sudo chroot squashfs-root systemctl restart ssh


echo 'nameserver 8.8.8.8' > squashfs-root/etc/resolv.conf

# Create ext4 filesystem image
CUSTOM_VM_DIR="${VM_DIR}/${OS_TYPE}.ext4"
sudo chown -R root:root squashfs-root
truncate -s ${DISK_SIZE_GB}G "${OS_TYPE}.ext4"
sudo mkfs.ext4 -d squashfs-root -F "${CUSTOM_VM_DIR}"

sudo chmod -R 777 "${VM_DIR}"

# Cleanup
cd - > /dev/null
sudo rm -rf "${VM_DIR}/${OS_TYPE}.squashfs.upstream"

echo "Custom rootfs created at: ${CUSTOM_VM_DIR}"