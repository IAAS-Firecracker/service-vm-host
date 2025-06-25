import os
import subprocess
import datetime
import json
import requests
import shutil
from dependencies import StandardResponse

def log(msg, log_path):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S,%3f')[:-3]
    with open(log_path, "a") as log_file:
        log_file.write(f"{timestamp} - setup_vm.py - INFO - {msg}\n")

def check_file_exists(path, log_path, error_msg):
    if not os.path.isfile(path):
        log(error_msg, log_path)
        raise FileNotFoundError(error_msg)

def check_curl_response(response, description, log_path):
    if not (200 <= response.status_code < 300):
        log(f"Error during {description}: {response.text}", log_path)
        raise Exception(f"{description} failed: {response.text}")

def configure_firecracker_vm(os_type, user_id, ssh_public_key, disk_size_gb, vm_name,
                             vcpu_count, mem_size_mib, tap_device, tap_ip, vm_ip, vm_mac):

    base_dir = "/opt/firecracker"
    vm_dir = f"{base_dir}/vm/{user_id}/{vm_name}"
    socket_path = f"/tmp/firecracker-sockets/{user_id}_{vm_name}.socket"
    custom_vm = f"{vm_dir}/{os_type}.ext4"
    kernel_path = f"{vm_dir}/vmlinux-5.10.225"
    log_path = f"{base_dir}/logs/firecracker-{user_id}_{vm_name}.log"
    iface_id = tap_device
    mask_short = "/30"

    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    os.chmod(os.path.dirname(log_path), 0o777)

    check_file_exists(kernel_path, log_path, f"Kernel file not found at {kernel_path}")
    check_file_exists(custom_vm, log_path, f"Custom VM image not found at {custom_vm}")

    # TAP setup
    subprocess.run(["sudo", "ip", "link", "del", tap_device], stderr=subprocess.DEVNULL)
    subprocess.run(["sudo", "ip", "tuntap", "add", "dev", tap_device, "mode", "tap"], check=True)
    subprocess.run(["sudo", "ip", "addr", "add", f"{tap_ip}{mask_short}", "dev", tap_device], check=True)
    subprocess.run(["sudo", "ip", "link", "set", "dev", tap_device, "up"], check=True)
    subprocess.run(["sudo", "sh", "-c", "echo 1 > /proc/sys/net/ipv4/ip_forward"], check=True)

    host_iface = subprocess.check_output(["ip", "-j", "route", "list", "default"])
    host_iface = json.loads(host_iface)[0]["dev"]

    subprocess.run(["sudo", "iptables", "-P", "FORWARD", "ACCEPT"], check=True)
    subprocess.run(["sudo", "iptables", "-t", "nat", "-D", "POSTROUTING", "-o", host_iface, "-j", "MASQUERADE"], stderr=subprocess.DEVNULL)
    subprocess.run(["sudo", "iptables", "-t", "nat", "-A", "POSTROUTING", "-o", host_iface, "-j", "MASQUERADE"], check=True)
    subprocess.run(["sudo", "ip", "route", "add", "default", "via", tap_ip, "dev", tap_device], check=True)
    subprocess.run(["sudo", "sh", "-c", "echo 'nameserver 8.8.8.8' > /etc/resolv.conf"], check=True)

    # Firecracker API config
    def put(endpoint, data):
        return requests.put(
            f"http://localhost{endpoint}",
            headers={'Accept': 'application/json', 'Content-Type': 'application/json'},
            data=json.dumps(data),
            unix_socket=socket_path
        )

    def curl_socket_put(endpoint, data):
        return requests.request(
            method='PUT',
            url=f"http://localhost{endpoint}",
            headers={'Accept': 'application/json', 'Content-Type': 'application/json'},
            data=json.dumps(data),
            unix_socket_path=socket_path
        )

    requests_unixsocket_monkey_patch()

    check_curl_response(put("/machine-config", {
        "vcpu_count": vcpu_count,
        "mem_size_mib": mem_size_mib,
        "smt": False
    }), "Configuring VM machine config", log_path)

    check_curl_response(put("/boot-source", {
        "kernel_image_path": kernel_path,
        "boot_args": "console=ttyS0 reboot=k panic=1 pci=off"
    }), "Configuring kernel", log_path)

    check_curl_response(put("/drives/rootfs", {
        "drive_id": "rootfs",
        "path_on_host": custom_vm,
        "is_root_device": True,
        "is_read_only": False
    }), "Configuring rootfs", log_path)

    check_curl_response(put(f"/network-interfaces/{iface_id}", {
        "iface_id": iface_id,
        "guest_mac": vm_mac,
        "host_dev_name": tap_device
    }), "Configuring network interface", log_path)

    check_curl_response(put("/balloon", {
        "amount_mib": 512,
        "deflate_on_oom": True,
        "stats_polling_interval_s": 1
    }), "Configuring balloon", log_path)

    # Network config inside guest
    mount_dir = "/mnt"
    os.makedirs(mount_dir, exist_ok=True)
    subprocess.run(["sudo", "mount", "-o", "loop", custom_vm, mount_dir], check=True)

    netplan_path = os.path.join(mount_dir, "etc/netplan/01-netcfg.yaml")
    os.makedirs(os.path.dirname(netplan_path), exist_ok=True)
    with open(netplan_path, "w") as f:
        f.write(f"""
network:
  version: 2
  renderer: networkd
  ethernets:
    {iface_id}:
      addresses: ["{vm_ip}{mask_short}"]
      routes:
        - to: default
          via: {tap_ip}
      nameservers:
        addresses: [8.8.8.8]
      dhcp4: false
""")
    subprocess.run(["sudo", "chroot", mount_dir, "netplan", "generate"], check=True)
    subprocess.run(["sudo", "chroot", mount_dir, "netplan", "apply"], check=True)
    subprocess.run(["sudo", "umount", mount_dir], check=True)

    log("VM configuration completed successfully", log_path)


# Support for requests over UNIX socket
def requests_unixsocket_monkey_patch():
    import requests_unixsocket
    from requests_unixsocket import Session
    requests.Session.request = Session().request

