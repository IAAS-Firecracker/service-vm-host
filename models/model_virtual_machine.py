#!/usr/bin/env python3
from sqlalchemy import Column, BigInteger, ForeignKey, Boolean, Enum, DateTime, Numeric, Integer, String, Text, Float
from pydantic import BaseModel
from database import Base
from datetime import datetime
from typing import Optional
from sqlalchemy.sql import func

class VirtualMachine(Base):
    __tablename__ = 'virtual_machines'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    ssh_key_id = Column(BigInteger, ForeignKey('ssh_keys.id'), nullable=True)
    name = Column(String(255), nullable=False)
    vcpu_count = Column(Integer, nullable=True)
    memory_size_mib = Column(Integer, nullable=True)
    disk_size_gb = Column(Integer, nullable=True)
    kernel_image_path = Column(String(255), nullable=True)
    rootfs_path = Column(String(255), nullable=True)
    mac_address = Column(String(255), nullable=True)
    ip_address = Column(String(255), nullable=True)
    tap_device_name = Column(String(255), nullable=True)
    tap_ip = Column(String(255), nullable=True)
    network_namespace = Column(String(255), nullable=True)
    allow_mmds_requests = Column(Boolean, default=False, nullable=False)
    boot_args = Column(Text, nullable=True)
    track_dirty_pages = Column(Boolean, default=True, nullable=False)
    rx_rate_limiter_bandwidth = Column(Integer, nullable=True)
    tx_rate_limiter_bandwidth = Column(Integer, nullable=True)
    balloon_size_mib = Column(Integer, nullable=True)
    balloon_deflate_on_oom = Column(Boolean, default=True, nullable=False)
    status = Column(Enum('creating', 'created', 'starting', 'running', 'stopping', 'stopped', 'error', 'deleted', 
                         name='vm_status_enum'), default='creating', nullable=False)
    socket_path = Column(String(255), nullable=True)
    log_path = Column(String(255), nullable=True)
    pid_file_path = Column(String(255), nullable=True)
    pid = Column(Integer, nullable=True)
    last_start_time = Column(DateTime, nullable=True)
    last_stop_time = Column(DateTime, nullable=True)
    last_error_time = Column(DateTime, nullable=True)
    last_error_message = Column(Text, nullable=True)
    cpu_usage_percent = Column(Float, nullable=True)
    memory_usage_mib = Column(Integer, nullable=True)
    disk_usage_bytes = Column(Integer, nullable=True)
    network_rx_bytes = Column(BigInteger, nullable=True)
    network_tx_bytes = Column(BigInteger, nullable=True)
    ssh_port = Column(Integer, nullable=True)
    root_password_hash = Column(String(255), nullable=True)
    is_locked = Column(Boolean, default=False, nullable=False)
    locked_at = Column(DateTime, nullable=True)
    locked_by = Column(String(255), nullable=True)
    billing_start_time = Column(DateTime, nullable=True)
    total_running_hours = Column(Numeric(10, 2), default=0.00, nullable=False)
    total_cost = Column(Numeric(10, 2), default=0.00, nullable=False)
    system_image_id = Column(BigInteger, nullable=True)
    vm_offer_id = Column(BigInteger, nullable=True)
    service_cluster_id = Column(BigInteger, nullable=True)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'ssh_key_id': self.ssh_key_id,
            'name': self.name,
            'vcpu_count': self.vcpu_count,
            'memory_size_mib': self.memory_size_mib,
            'disk_size_gb': self.disk_size_gb,
            'kernel_image_path': self.kernel_image_path,
            'rootfs_path': self.rootfs_path,
            'mac_address': self.mac_address,
            'ip_address': self.ip_address,
            'tap_device_name': self.tap_device_name,
            'tap_ip': self.tap_ip,
            'network_namespace': self.network_namespace,
            'allow_mmds_requests': self.allow_mmds_requests,
            'boot_args': self.boot_args,
            'track_dirty_pages': self.track_dirty_pages,
            'rx_rate_limiter_bandwidth': self.rx_rate_limiter_bandwidth,
            'tx_rate_limiter_bandwidth': self.tx_rate_limiter_bandwidth,
            'balloon_size_mib': self.balloon_size_mib,
            'balloon_deflate_on_oom': self.balloon_deflate_on_oom,
            'status': self.status,
            'socket_path': self.socket_path,
            'log_path': self.log_path,
            'pid_file_path': self.pid_file_path,
            'pid': self.pid,
            'last_start_time': self.last_start_time,
            'last_stop_time': self.last_stop_time,
            'last_error_time': self.last_error_time,
            'last_error_message': self.last_error_message,
            'cpu_usage_percent': self.cpu_usage_percent,
            'memory_usage_mib': self.memory_usage_mib,
            'disk_usage_bytes': self.disk_usage_bytes,
            'network_rx_bytes': self.network_rx_bytes,
            'network_tx_bytes': self.network_tx_bytes,
            'ssh_port': self.ssh_port,
            'root_password_hash': self.root_password_hash,
            'is_locked': self.is_locked,
            'locked_at': self.locked_at,
            'locked_by': self.locked_by,
            'billing_start_time': self.billing_start_time,
            'total_running_hours': self.total_running_hours,
            'total_cost': self.total_cost,
            'system_image_id': self.system_image_id,
            'vm_offer_id': self.vm_offer_id,
            'service_cluster_id': self.service_cluster_id,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }


class VirtualMachineBase(BaseModel):
    name: str
    user_id: str  # Identifiant unique de l'utilisateur
    service_cluster_id: int
    cpu_count: int
    memory_size_mib: int
    disk_size_gb: int
    os_type: str  # 'ubuntu-24.04', 'ubuntu-22.04', 'alpine', 'centos'
    ssh_public_key: Optional[str] = None  # Clé SSH publique de l'utilisateur
    root_password: Optional[str] = None
    tap_device: Optional[str] = "tap0"
    tap_ip: Optional[str] = "172.16.0.1"
    vm_ip: Optional[str] = "172.16.0.2"
    vm_mac: Optional[str] = "00:00:00:00:00:00"
    vm_offer_id: int
    system_image_id: int

class VMStartConfig(BaseModel):
    user_id: str  
    vm_id: int

class VMStopConfig(BaseModel):
    user_id: str  
    vm_id: int

class VMDeleteConfig(BaseModel):
    user_id: str  
    vm_id: int

class VMStatusConfig(BaseModel):
    user_id: str  
    vm_id: int

class VMStatus(BaseModel):
    name: str
    status: str
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    uptime: Optional[str] = None

class VirtualMachineCreate(VirtualMachineBase):
    pass


class VirtualMachineUpdate(VirtualMachineBase):
    pass


class VirtualMachineResponse(VirtualMachineBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MetricsUpdate(BaseModel):
    user_id: int
    vm_id: int
    cpu_usage: float
    memory_usage: float
    disk_usage: float