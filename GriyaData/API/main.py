import os
import shutil
from datetime import datetime

from fastapi import FastAPI, Depends, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from database import models
from database import engine, get_db
from database import schemas

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="API GriyaData",
              description="API Manajemen Penjualan GriyaData — schema lengkap")

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


# ROOT
@app.get("/")
def read_root():
    return {"message": "API GriyaData berhasil terhubung ke Database Supabase."}


# AUTH
@app.post("/api/login")
def login_admin(request: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        models.User.username == request.username).first()
    if user and user.password == request.password:
        return {"status": "success", "message": "Login berhasil",
                "token": "token_rahasia_griyadata_123"}
    raise HTTPException(status_code=400, detail="Username atau password salah")


# PRODUCTS
def _product_dict(p) -> dict:
    return {"id": p.id, "product_name": p.product_name,
            "category": p.category, "price": p.price}


@app.get("/api/products")
def get_all_products(db: Session = Depends(get_db)):
    prods = db.query(models.Product).order_by(models.Product.product_name).all()
    return {"total_data": len(prods), "data": [_product_dict(p) for p in prods]}


@app.post("/api/products")
def create_product(data: schemas.ProductCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Product).filter(
        models.Product.product_name == data.product_name).first()
    if existing:
        return {"message": "Produk sudah ada.", "data": _product_dict(existing)}
    p = models.Product(product_name=data.product_name,
                       category=data.category, price=data.price)
    db.add(p); db.commit(); db.refresh(p)
    return {"message": "Produk berhasil ditambahkan!", "data": _product_dict(p)}


@app.put("/api/products/{product_id}")
def update_product(product_id: int, data: schemas.ProductUpdate,
                   db: Session = Depends(get_db)):
    p = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not p:
        raise HTTPException(404, "Produk tidak ditemukan")
    if data.product_name is not None: p.product_name = data.product_name
    if data.category     is not None: p.category     = data.category
    if data.price        is not None: p.price        = data.price
    db.commit(); db.refresh(p)
    return {"message": f"Produk ID {product_id} diperbarui.", "data": _product_dict(p)}


@app.delete("/api/products/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db)):
    p = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not p:
        raise HTTPException(404, "Produk tidak ditemukan")
    db.delete(p); db.commit()
    return {"message": f"Produk ID {product_id} berhasil dihapus."}


# ORDERS
def _parse_date(s) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s))
    except Exception:
        return None


def _order_dict(o) -> dict:
    return {
        "id":                      o.id,
        "order_id":                o.order_id,
        "customer_name":           o.customer_name,
        "product_id":              o.product_id,
        "quantity":                o.quantity,
        "discount":                o.discount,
        "total":                   o.total,
        "shipping_fee":            o.shipping_fee,
        "total_sales":             o.total_sales,
        "status":                  o.status,
        "shipping_address":        o.shipping_address,
        "customer_gender":         o.customer_gender,
        "customer_city":           o.customer_city,
        "payment_method":          o.payment_method,
        "courier":                 o.courier,
        "estimated_delivery_days": o.estimated_delivery_days,
        "sales_channel":           o.sales_channel,
        "customer_rating":         o.customer_rating,
        "sales_date":              o.sales_date.isoformat() if o.sales_date else None,
    }


@app.get("/api/orders")
def get_all_orders(db: Session = Depends(get_db)):
    orders = db.query(models.Order).all()
    return {"total_data": len(orders), "data": [_order_dict(o) for o in orders]}


@app.post("/api/orders")
def create_order(data: schemas.OrderCreate, db: Session = Depends(get_db)):
    ts = data.total_sales if data.total_sales is not None \
        else (data.total or 0) + (data.shipping_fee or 0)
    o = models.Order(
        order_id=data.order_id,
        customer_name=data.customer_name,
        product_id=data.product_id,
        quantity=data.quantity,
        discount=data.discount or 0,
        total=data.total,
        shipping_fee=data.shipping_fee or 0,
        total_sales=ts,
        status=data.status or "Pending",
        shipping_address=data.shipping_address or "",
        customer_gender=data.customer_gender or "",
        customer_city=data.customer_city or "",
        payment_method=data.payment_method or "Offline/COD",
        courier=data.courier or "",
        estimated_delivery_days=data.estimated_delivery_days or 0,
        sales_channel=data.sales_channel or "",
        customer_rating=data.customer_rating or 0,
        sales_date=_parse_date(data.sales_date),
    )
    db.add(o); db.commit(); db.refresh(o)
    return {"message": "Pesanan berhasil dicatat!", "data": _order_dict(o)}


@app.put("/api/orders/{order_id}")
def update_order_status(order_id: int, request: schemas.OrderUpdate,
                        db: Session = Depends(get_db)):
    o = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not o:
        raise HTTPException(404, "Pesanan tidak ditemukan")
    o.status = request.status
    db.commit(); db.refresh(o)
    return {"message": f"Status pesanan ID {order_id} → {request.status}",
            "data": _order_dict(o)}


@app.delete("/api/orders/{order_id}")
def delete_order(order_id: int, db: Session = Depends(get_db)):
    o = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not o:
        raise HTTPException(404, "Pesanan tidak ditemukan")
    db.delete(o); db.commit()
    return {"message": f"Pesanan ID {order_id} berhasil dihapus."}


@app.post("/api/orders/bulk")
def bulk_insert_orders(payload: schemas.BulkOrderCreate,
                       db: Session = Depends(get_db)):
    inserted, skipped, errors = 0, 0, []
    for idx, od in enumerate(payload.orders):
        try:
            ts = od.total_sales if od.total_sales is not None \
                else (od.total or 0) + (od.shipping_fee or 0)
            o = models.Order(
                order_id=od.order_id,
                customer_name=od.customer_name,
                product_id=od.product_id,
                quantity=od.quantity,
                discount=od.discount or 0,
                total=od.total,
                shipping_fee=od.shipping_fee or 0,
                total_sales=ts,
                status=od.status or "Pending",
                shipping_address=od.shipping_address or "",
                customer_gender=od.customer_gender or "",
                customer_city=od.customer_city or "",
                payment_method=od.payment_method or "Offline/COD",
                courier=od.courier or "",
                estimated_delivery_days=od.estimated_delivery_days or 0,
                sales_channel=od.sales_channel or "",
                customer_rating=od.customer_rating or 0,
                sales_date=_parse_date(od.sales_date),
            )
            db.add(o); inserted += 1
        except Exception as e:
            skipped += 1; errors.append(f"Baris {idx+1}: {e}")
    db.commit()
    return {"message": f"Bulk insert selesai. {inserted} berhasil, {skipped} dilewati.",
            "inserted": inserted, "skipped": skipped, "errors": errors[:10]}

# FILE UPLOAD
@app.post("/api/upload")
def upload_file(file: UploadFile = File(...)):
    loc = f"uploads/{file.filename}"
    with open(loc, "wb") as buf:
        shutil.copyfileobj(file.file, buf)
    return {"message": "File berhasil diunggah!", "filename": file.filename,
            "file_path": f"/uploads/{file.filename}"}
