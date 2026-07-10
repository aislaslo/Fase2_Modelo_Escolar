FROM python:3.11-slim

WORKDIR /app

# Evita archivos .pyc y fuerza salida sin buffer para logs en tiempo real.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Instalacion de dependencias en una capa separada para aprovechar la cache.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia del codigo fuente y del artefacto del modelo ya entrenado.
COPY src/ ./src/
COPY models/ ./models/

EXPOSE 8000

# Usa $PORT si el entorno lo define (ej. Render), y 8000 como valor por
# defecto para ejecucion local (docker run -p 8000:8000 ...).
CMD ["sh", "-c", "uvicorn src.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
