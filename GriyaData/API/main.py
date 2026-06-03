import os
import shutil
from fastapi import FastAPI, Depends, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi import HTTPException
from sqlalchemy.orm import Session
import models
from database import engine, get_db
import schemas

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="API GriyaData",
    description="API untuk Aplikasi Manajemen Penjualan Toko Miniatur"
)

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


# ─────────────────────────────────────────────
# ROOT
# ─────────────────────────────────────────────
@app.get("/")
def read_root():
    return {"message": "Selamat! API GriyaData berhasil terhubung ke Database Supabase."}


# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────
@app.post("/api/login")
def login_admin(request: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == request.username).first()
    if user and user.password == request.password:
        return {
            "status": "success",
            "message": "Login berhasil",
            "token": "token_rahasia_griyadata_123"
        }
    raise HTTPException(status_code=400, detail="Username atau password salah")


# ─────────────────────────────────────────────
# PRODUCTS
# ─────────────────────────────────────────────
@app.get("/api/products")
def get_all_products(db: Session = Depends(get_db)):
    """Ambil semua produk dari tabel products."""
    products = db.query(models.Product).order_by(models.Product.nama_barang).all()
    return {
        "total_data": len(products),
        "data": [
            {
                "id": p.id,
                "nama_barang": p.nama_barang,
                "kategori": p.kategori,
                "harga": p.harga
            }
            for p in products
        ]
    }

@app.post("/api/products")
def create_product(product_data: schemas.ProductCreate, db: Session = Depends(get_db)):
    """Tambah produk baru."""
    # Cek duplikat nama barang
    existing = db.query(models.Product).filter(
        models.Product.nama_barang == product_data.nama_barang
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Produk '{product_data.nama_barang}' sudah ada di database."
        )
    db_product = models.Product(
        nama_barang=product_data.nama_barang,
        kategori=product_data.kategori,
        harga=product_data.harga
    )
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return {
        "message": "Produk berhasil ditambahkan!",
        "data": {
            "id": db_product.id,
            "nama_barang": db_product.nama_barang,
            "kategori": db_product.kategori,
            "harga": db_product.harga
        }
    }

@app.delete("/api/products/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db)):
    """Hapus produk berdasarkan ID."""
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan")
    db.delete(product)
    db.commit()
    return {"message": f"Produk ID {product_id} berhasil dihapus."}


# ─────────────────────────────────────────────
# ORDERS
# ─────────────────────────────────────────────
@app.post("/api/orders")
def create_order(order_data: schemas.OrderCreate, db: Session = Depends(get_db)):
    """Catat pesanan baru."""
    db_order = models.Order(
        nama_pelanggan=order_data.nama_pelanggan,
        product_id=order_data.product_id,
        jumlah=order_data.jumlah,
        total_harga=order_data.total_harga
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return {
        "message": "Berhasil mencatat pesanan baru!",
        "data": db_order
    }

@app.get("/api/orders")
def get_all_orders(db: Session = Depends(get_db)):
    """Ambil semua pesanan."""
    orders = db.query(models.Order).all()
    return {
        "total_data": len(orders),
        "data": orders
    }

@app.put("/api/orders/{order_id}")
def update_order_status(order_id: int, request: schemas.OrderUpdate, db: Session = Depends(get_db)):
    """Update status pesanan."""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pesanan tidak ditemukan")
    order.status_pesanan = request.status_pesanan
    db.commit()
    db.refresh(order)
    return {
        "message": f"Status pesanan ID {order_id} berhasil diperbarui menjadi {request.status_pesanan}",
        "data": order
    }

@app.delete("/api/orders/{order_id}")
def delete_order(order_id: int, db: Session = Depends(get_db)):
    """Hapus pesanan."""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pesanan tidak ditemukan")
    db.delete(order)
    db.commit()
    return {"message": f"Pesanan ID {order_id} berhasil dihapus dari sistem."}


# ─────────────────────────────────────────────
# BULK INSERT ORDERS dari data eksternal
# (dipakai saat import CSV/Excel dari desktop app)
# ─────────────────────────────────────────────
@app.post("/api/orders/bulk")
def bulk_insert_orders(payload: schemas.BulkOrderCreate, db: Session = Depends(get_db)):
    """
    Insert banyak pesanan sekaligus.
    Menerima list of order dalam satu request.
    Mengembalikan jumlah data yang berhasil diinsert.
    """
    inserted = 0
    skipped  = 0
    errors   = []

    for idx, order_data in enumerate(payload.orders):
        try:
            db_order = models.Order(
                nama_pelanggan=order_data.nama_pelanggan,
                product_id=order_data.product_id,
                jumlah=order_data.jumlah,
                total_harga=order_data.total_harga
            )
            db.add(db_order)
            inserted += 1
        except Exception as e:
            skipped += 1
            errors.append(f"Baris {idx + 1}: {str(e)}")

    db.commit()
    return {
        "message": f"Bulk insert selesai. {inserted} pesanan berhasil, {skipped} dilewati.",
        "inserted": inserted,
        "skipped": skipped,
        "errors": errors[:10]  # Tampilkan maks 10 error pertama
    }


# ─────────────────────────────────────────────
# FILE UPLOAD (opsional, tetap dipertahankan)
# ─────────────────────────────────────────────
@app.post("/api/upload")
def upload_file(file: UploadFile = File(...)):
    file_location = f"uploads/{file.filename}"
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {
        "message": "File berhasil diunggah!",
        "filename": file.filename,
        "file_path": f"/uploads/{file.filename}"
    }

# ==========================================
# TAMBAHAN API UNTUK PRODUK & BULK IMPORT 
# ==========================================

# 1. GET /api/products — Ambil semua produk (Untuk Dropdown Jaye)
@app.get("/api/products")
def get_all_products(db: Session = Depends(get_db)):
    products = db.query(models.Product).all()
    return {
        "total_data": len(products),
        "data": products
    }

# 2. POST /api/products — Tambah produk baru
@app.post("/api/products")
def create_product(product_data: schemas.ProductCreate, db: Session = Depends(get_db)):
    db_product = models.Product(
        nama_barang=product_data.nama_barang,
        kategori=product_data.kategori,
        harga=product_data.harga
    )
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return {
        "message": "Produk berhasil ditambahkan!",
        "data": db_product
    }

# 3. DELETE /api/products/{id} — Hapus produk
@app.delete("/api/products/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan")
    
    db.delete(product)
    db.commit()
    return {"message": f"Produk ID {product_id} berhasil dihapus"}

# 4. POST /api/orders/bulk — Insert banyak pesanan sekaligus (Import CSV/Excel)
@app.post("/api/orders/bulk")
def create_bulk_orders(bulk_data: schemas.BulkOrderCreate, db: Session = Depends(get_db)):
    inserted = 0
    errors = []
    
    for order_data in bulk_data.orders:
        try:
            db_order = models.Order(
                nama_pelanggan=order_data.nama_pelanggan,
                product_id=order_data.product_id,
                jumlah=order_data.jumlah,
                total_harga=order_data.total_harga
            )
            db.add(db_order)
            inserted += 1
        except Exception as e:
            errors.append(str(e))
    
    db.commit() 
    
    return {
        "message": "Bulk insert selesai",
        "inserted": inserted,
        "skipped": len(bulk_data.orders) - inserted,
        "errors": errors
    }