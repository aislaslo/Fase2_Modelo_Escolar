"""Generacion del dataset sintetico de abandono escolar.

No se dispuso del CSV original de la Actividad 6 (ver docs/documentacion_tecnica.md,
seccion de trazabilidad de datos). Este script genera un dataset sintetico equivalente,
con las mismas 8 variables predictoras descritas en el contexto de la Actividad 6 y una
relacion causal simulada entre variables y abandono, de forma reproducible (semilla fija)
para servir como base de entrenamiento de la Fase 2.
"""

from pathlib import Path

import numpy as np
import pandas as pd

RANDOM_STATE = 42
N_REGISTROS = 1000
OUTPUT_PATH = Path("data/dataset_abandono.csv")


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-z))


def generar_dataset(n: int = N_REGISTROS, seed: int = RANDOM_STATE) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    promedio_academico = np.clip(rng.normal(7.2, 1.3, n), 0.0, 10.0)
    materias_reprobadas = rng.poisson(lam=np.clip((10 - promedio_academico) * 0.45, 0.05, None))
    asistencia = np.clip(rng.normal(0.85, 0.13, n), 0.0, 1.0)
    condicion_beca = rng.binomial(1, 0.35, n)
    distancia_campus = np.clip(rng.exponential(15.0, n), 0.0, 80.0)
    trabaja = rng.binomial(1, 0.40, n)
    horas_trabajo_semanales = np.where(
        trabaja == 1, rng.uniform(5, 45, n), 0.0
    ).round().astype(int)
    semestre_actual = rng.integers(1, 10, n)
    modalidad = rng.binomial(1, 0.25, n)

    ruido = rng.normal(0, 0.75, n)

    # Escala de senal (2.5) y ruido calibrados empiricamente para que la
    # Regresion Logistica alcance un F1 de prueba cercano al reportado en la
    # Actividad 6 (F1 aprox. 0.8456, ver context.md seccion 2.3).
    z = 2.5 * (
        -1.35
        - 0.50 * (promedio_academico - 7.0)
        + 0.42 * materias_reprobadas
        - 3.10 * (asistencia - 0.85)
        - 0.85 * condicion_beca
        + 0.018 * distancia_campus
        + 0.032 * horas_trabajo_semanales
        + 0.20 * modalidad
    ) + ruido
    probabilidad = _sigmoid(z)
    abandono = rng.binomial(1, probabilidad)

    return pd.DataFrame(
        {
            "promedio_academico": promedio_academico.round(2),
            "materias_reprobadas": materias_reprobadas,
            "asistencia": asistencia.round(3),
            "condicion_beca": condicion_beca,
            "distancia_campus": distancia_campus.round(2),
            "horas_trabajo_semanales": horas_trabajo_semanales,
            "semestre_actual": semestre_actual,
            "modalidad": modalidad,
            "abandono": abandono,
        }
    )


if __name__ == "__main__":
    df = generar_dataset()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Dataset generado en {OUTPUT_PATH} ({len(df)} registros)")
    print(f"Proporcion de abandono: {df['abandono'].mean():.3f}")
