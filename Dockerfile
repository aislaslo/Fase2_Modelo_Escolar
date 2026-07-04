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

CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
