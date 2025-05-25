from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, func
from pydantic import BaseModel
from datetime import datetime
from database import Base


class UserEntity(Base):
    __tablename__ = "user"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True)
    email = Column(String(255), unique=True, index=True)
    password = Column(String(255))
    role = Column(String(255))
    token = Column(String(255))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "token": self.token,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


class UserBase(BaseModel):
    name: str
    email: str
    password: str
    role: str
    token: str


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    token: Optional[str] = None
    

class UserResponse(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
        