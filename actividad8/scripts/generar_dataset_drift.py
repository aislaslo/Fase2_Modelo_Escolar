"""Genera un dataset sintetico que simula datos de produccion con drift,
para demostrar la deteccion de data drift (Actividad 8).

Reutiliza el generador de la Fase 2 (src/generate_data.py) como base, pero
desplaza deliberadamente algunas distribuciones para simular un escenario
realista: un semestre con mas dificultades economicas (mas horas de trabajo,
menor asistencia) y mayor adopcion de modalidad en linea.

No reemplaza data/dataset_abandono.csv (el dataset de entrenamiento); genera
un archivo separado que representa "nuevos registros observados en
produccion" a comparar contra el dataset de entrenamiento.
"""

from pathlib import Path

import numpy as np
import pandas as pd

RANDOM_STATE = 123  # distinto de la Fase 2 (42) para no reproducir el mismo dataset
N_REGISTROS = 300
OUTPUT_PATH = Path("actividad8/evidencia/dataset_produccion_con_drift.csv")


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-z))


def generar_dataset_con_drift(n: int = N_REGISTROS, seed: int = RANDOM_STATE) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    # --- Variables con drift deliberado respecto al dataset de entrenamiento ---
    # promedio_academico: se desplaza ligeramente hacia abajo (media 7.2 -> 6.5)
    promedio_academico = np.clip(rng.normal(6.5, 1.4, n), 0.0, 10.0)
    # horas_trabajo_semanales: mas estudiantes trabajan, y trabajan mas horas
    # (60% trabaja en el dataset original -> 65% aqui; rango 5-45 -> 10-48)
    trabaja = rng.binomial(1, 0.65, n)
    horas_trabajo_semanales = np.where(
        trabaja == 1, rng.uniform(10, 48, n), 0.0
    ).round().astype(int)
    # asistencia: cae ligeramente (media 0.85 -> 0.78)
    asistencia = np.clip(rng.normal(0.78, 0.15, n), 0.0, 1.0)
    # modalidad: mayor adopcion de modalidad en linea (25% -> 45%)
    modalidad = rng.binomial(1, 0.45, n)

    # --- Variables sin drift intencional (misma distribucion que Fase 2) ---
    materias_reprobadas = rng.poisson(lam=np.clip((10 - promedio_academico) * 0.45, 0.05, None))
    condicion_beca = rng.binomial(1, 0.35, n)
    distancia_campus = np.clip(rng.exponential(15.0, n), 0.0, 80.0)
    semestre_actual = rng.integers(1, 10, n)

    ruido = rng.normal(0, 0.75, n)
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
    df = generar_dataset_con_drift()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Dataset de produccion (con drift) generado en {OUTPUT_PATH} ({len(df)} registros)")
    print(f"Proporcion de abandono: {df['abandono'].mean():.3f}")
