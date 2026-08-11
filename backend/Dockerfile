FROM python:3.11-slim

WORKDIR /app

# System dependencies for PostGIS/psycopg2/PDF parsing
RUN apt-get update && apt-get install -y \
    libpq-dev gcc g++ \
    libgdal-dev \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --default-timeout=1000 --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
