from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from database import Base

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    nama_barang = Column(String, index=True)
    kategori = Column(String)
    harga = Column(Float)

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    nama_pelanggan = Column(String)
    product_id = Column(Integer, ForeignKey("products.id"))
    jumlah = Column(Integer)
    total_harga = Column(Float)
    tanggal_pesanan = Column(DateTime(timezone=True), server_default=func.now())
    status_pesanan = Column(String, default="Pending")
    metode_pembayaran = Column(String, default="Offline/COD") 

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String) # Untuk kebutuhan tugas/MVP, kita simpan string teks biasa dulu