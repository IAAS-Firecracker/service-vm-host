from sqlalchemy import Column, String, Text, DateTime, BigInteger, func
from datetime import datetime
from database import Base
from pydantic import BaseModel
from typing import Optional

class SSHKey(Base):
    __tablename__ = 'ssh_keys'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    name = Column(String(255), nullable=False)
    public_key = Column(Text, nullable=False)
    private_key = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'public_key': self.public_key,
            'private_key': self.private_key,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }


# Modèles Pydantic pour la validation des données
class SSHKeyBase(BaseModel):
    name: str
    public_key: Optional[str] = None
    private_key: Optional[str] = None

class SSHKeyCreate(SSHKeyBase):
    pass

class SSHKeyUpdate(SSHKeyBase):
    name: Optional[str] = None
    public_key: Optional[str] = None
    private_key: Optional[str] = None

class SSHKeyResponse(SSHKeyBase):
    id: int
    public_key: Optional[str] = None
    private_key: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True