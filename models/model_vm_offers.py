#!/usr/bin/env python3
from typing import Optional
from sqlalchemy import Column, Integer, String, Text, DateTime, func
from sqlalchemy.types import Numeric, Boolean
from pydantic import BaseModel
from datetime import datetime
from database import Base

class VMOfferEntity(Base):
    __tablename__ = 'vm_offers'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    cpu_count = Column(Integer, nullable=False)
    memory_size_mib = Column(Integer, nullable=False)
    disk_size_gb = Column(Integer, nullable=False)
    price_per_hour = Column(Numeric(10, 2), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'cpu_count': self.cpu_count,
            'memory_size_mib': self.memory_size_mib,
            'disk_size_gb': self.disk_size_gb,
            'price_per_hour': self.price_per_hour,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class VMOfferBase(BaseModel):
    name: str
    description: str
    cpu_count: int
    memory_size_mib: int
    disk_size_gb: int
    price_per_hour: float
    is_active: Optional[bool] = True
    

class VMOfferCreate(VMOfferBase):
    pass

class VMOfferUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    cpu_count: Optional[int] = None
    memory_size_mib: Optional[int] = None
    disk_size_gb: Optional[int] = None
    price_per_hour: Optional[float] = None
    is_active: Optional[bool] = None
    

class VMOfferResponse(VMOfferBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        # orm_mode = True
        from_attributes = True