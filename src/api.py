"""API REST para el modelo de prediccion de abandono escolar."""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from src.inference import cargar_modelo, predecir
from src.schema import EstudianteEntrada, PrediccionSalida

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Precarga el modelo al iniciar el servicio para evitar latencia inicial.

    Si el artefacto no esta disponible, no se interrumpe el arranque: /health
    debe seguir respondiendo para que un orquestador (Docker, PaaS) distinga
    entre "proceso caido" y "proceso activo pero sin modelo cargado", y
    /predict reporta 503 en ese caso.
    """
    try:
        cargar_modelo()
    except FileNotFoundError as error:
        logger.warning("Modelo no disponible al iniciar: %s", error)
    yield


app = FastAPI(
    title="API de Prediccion de Abandono Escolar",
    description="Servicio de inferencia del modelo de Regresion Logistica "
    "desarrollado en la Actividad 6.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict:
    """Endpoint de verificacion de disponibilidad del servicio."""
    return {"estado": "operativo"}


@app.post("/predict", response_model=PrediccionSalida)
def predict(estudiante: EstudianteEntrada) -> PrediccionSalida:
    """Devuelve la prediccion de riesgo de abandono para un estudiante."""
    # INCIDENTE SIMULADO (Actividad 8): demora artificial para reproducir una
    # dependencia lenta y disparar ALERT-LAT-01. Se revierte en el rollback.
    time.sleep(3.5)
    try:
        resultado = predecir(estudiante.model_dump())
    except FileNotFoundError as error:
        raise HTTPException(status_code=503, detail=str(error))
    except Exception as error:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Error de inferencia: {error}")
    return PrediccionSalida(**resultado)
