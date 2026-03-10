from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# Schema dasar untuk pelanggan, digunakan saat membuat atau mengupdate
class PelangganBase(BaseModel):
    nama: Optional[str] = None
    nomor_hp: str
    kelas_notifikasi: List[int] = Field(default_factory=lambda: [4])
    whatsapp: Optional[bool] = False
    telegram: Optional[bool] = False

# Schema untuk membuat pelanggan baru (semua field opsional kecuali nomor_hp)
class PelangganCreate(PelangganBase):
    pass

class PelangganUpdate(BaseModel):
    nama: Optional[str] = None
    idpel: Optional[str] = None
    kelas_notifikasi: Optional[List[int]] = None
    telegram: Optional[bool] = None
    whatsapp: Optional[bool] = None
    telegram_chat_id: Optional[str] = None

# Schema untuk menampilkan data pelanggan, termasuk ID dari database
class Pelanggan(PelangganBase):
    id: int
    class Config:
        from_attributes = True

# Schema User & Token ---
class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# --- Schema Name Station Gateway ---
class NameStationBase(BaseModel):
    name_station: str
    singkatan_name_station: Optional[str] = None
    code_station: str
    keterangan: Optional[str] = None

class NameStationCreate(NameStationBase):
    pass

class NameStationUpdate(BaseModel):
    name_station: Optional[str] = None
    singkatan_name_station: Optional[str] = None
    code_station: Optional[str] = None
    keterangan: Optional[str] = None

class NameStation(NameStationBase):
    id: int
    create_date: Optional[datetime] = None
    update_date: Optional[datetime] = None
    class Config:
        from_attributes = True