from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Numeric, ForeignKey, Enum, BigInteger, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()

class SSHKey(Base):
    __tablename__ = 'ssh_keys'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    name = Column(String(255), nullable=False)
    public_key = Column(Text, nullable=False)
    private_key = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<SSHKey(id={self.id}, user_id={self.user_id}, name='{self.name}')>"


class SystemImage(Base):
    __tablename__ = 'system_images'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    os_type = Column(String(255), nullable=False)
    version = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    image_path = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<SystemImage(id={self.id}, name='{self.name}', os_type='{self.os_type}', version='{self.version}')>"



class VMOffer(Base):
    __tablename__ = 'vm_offers'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    cpu_count = Column(Integer, nullable=False)
    memory_size_mib = Column(Integer, nullable=False)
    disk_size_gb = Column(Integer, nullable=False)
    price_per_hour = Column(Numeric(10, 2), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<VMOffer(id={self.id}, name='{self.name}', cpu={self.cpu_count}, memory={self.memory_size_mib}, disk={self.disk_size_gb})>"


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
    
    def __repr__(self):
        return f"<VirtualMachine(id={self.id}, user_id={self.user_id}, name='{self.name}', status='{self.status}')>"

