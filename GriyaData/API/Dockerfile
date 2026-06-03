# Menggunakan Python versi ringan
FROM python:3.10-slim

# Menentukan folder kerja di dalam server
WORKDIR /app

# Menyalin file requirements dan menginstalnya
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Menyalin seluruh kode FastAPI kamu
COPY . .

# Membuka port 8080 untuk lalu lintas internet
EXPOSE 8080

# Perintah utama untuk menyalakan API
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]