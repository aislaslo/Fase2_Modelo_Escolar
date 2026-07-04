"""Carga del modelo serializado y logica de inferencia."""

from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd

MODEL_PATH = Path("models/modelo_abandono.joblib")
UMBRAL_DECISION = 0.40

FEATURE_ORDER = [
    "promedio_academico",
    "materias_reprobadas",
    "asistencia",
    "distancia_campus",
    "horas_trabajo_semanales",
    "semestre_actual",
    "condicion_beca",
    "modalidad",
]


@lru_cache(maxsize=1)
def cargar_modelo():
    """Carga el pipeline una sola vez y lo mantiene en memoria."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"No se encontro el modelo en {MODEL_PATH}. "
            "Ejecute primero src/generate_data.py y luego src/train.py."
        )
    return joblib.load(MODEL_PATH)


def _clasificar_riesgo(probabilidad: float) -> str:
    """Traduce la probabilidad a una categoria cualitativa de riesgo."""
    if probabilidad >= 0.70:
        return "alto"
    if probabilidad >= UMBRAL_DECISION:
        return "medio"
    return "bajo"


def predecir(entrada: dict) -> dict:
    """Genera la prediccion para un registro de estudiante."""
    modelo = cargar_modelo()
    df = pd.DataFrame([entrada])[FEATURE_ORDER]

    probabilidad = float(modelo.predict_proba(df)[:, 1][0])
    clase = int(probabilidad >= UMBRAL_DECISION)

    return {
        "probabilidad_abandono": round(probabilidad, 4),
        "clase_predicha": clase,
        "umbral_aplicado": UMBRAL_DECISION,
        "nivel_riesgo": _clasificar_riesgo(probabilidad),
    }
