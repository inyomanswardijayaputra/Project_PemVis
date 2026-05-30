from pydantic import BaseModel
from typing import List

# ── Auth ──────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str

# ── Products ──────────────────────────────────
class ProductCreate(BaseModel):
    nama_barang: str
    kategori: str
    harga: float

# ── Orders ────────────────────────────────────
class OrderCreate(BaseModel):
    nama_pelanggan: str
    product_id: int
    jumlah: int
    total_harga: float

class OrderUpdate(BaseModel):
    status_pesanan: str

# ── Bulk Orders (untuk import CSV/Excel) ──────
class BulkOrderCreate(BaseModel):
    orders: List[OrderCreate]
