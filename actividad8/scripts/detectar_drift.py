"""Deteccion de data drift entre el dataset de entrenamiento (Fase 2) y un
dataset que representa nuevos datos observados en produccion (Actividad 8).

Usa el Population Stability Index (PSI), el estandar mas comun en la
industria para monitoreo de drift en variables numericas y categoricas:

    PSI < 0.10               -> sin drift relevante
    0.10 <= PSI < 0.25        -> drift moderado (revisar)
    PSI >= 0.25               -> drift significativo (accion requerida)

Referencia: umbrales segun la practica estandar de PSI en monitoreo de
modelos de riesgo crediticio/educativo (ver docs/documento_tecnico.md,
seccion "Estrategias de deteccion de data drift").

Uso:
    python -m actividad8.scripts.detectar_drift
"""

from pathlib import Path

import mlflow
import numpy as np
import pandas as pd

REFERENCIA_PATH = Path("data/dataset_abandono.csv")
PRODUCCION_PATH = Path("actividad8/evidencia/dataset_produccion_con_drift.csv")
REPORTE_PATH = Path("actividad8/evidencia/reporte_drift.md")
EXPERIMENT_NAME = "actividad8_monitoreo_produccion"

FEATURES_NUMERICAS = [
    "promedio_academico", "materias_reprobadas", "asistencia",
    "distancia_campus", "horas_trabajo_semanales", "semestre_actual",
]
FEATURES_CATEGORICAS = ["condicion_beca", "modalidad"]

UMBRAL_MODERADO = 0.10
UMBRAL_SIGNIFICATIVO = 0.25
N_BINS = 10


def calcular_psi(referencia: pd.Series, produccion: pd.Series, n_bins: int = N_BINS) -> float:
    """Calcula el Population Stability Index entre dos distribuciones."""
    cuantiles = np.linspace(0, 1, n_bins + 1)
    bordes = np.unique(referencia.quantile(cuantiles).to_numpy())
    if len(bordes) < 3:
        bordes = np.array([referencia.min(), referencia.median(), referencia.max() + 1e-9])
    bordes[0] = -np.inf
    bordes[-1] = np.inf

    ref_bins = pd.cut(referencia, bins=bordes)
    prod_bins = pd.cut(produccion, bins=bordes)

    ref_pct = ref_bins.value_counts(normalize=True, sort=False).sort_index()
    prod_pct = prod_bins.value_counts(normalize=True, sort=False).sort_index()

    epsilon = 1e-4  # evita division/log de cero en bins vacios
    ref_pct = ref_pct.reindex(ref_pct.index, fill_value=0) + epsilon
    prod_pct = prod_pct.reindex(ref_pct.index, fill_value=0) + epsilon

    psi = float(((prod_pct - ref_pct) * np.log(prod_pct / ref_pct)).sum())
    return psi


def clasificar_psi(psi: float) -> str:
    if psi >= UMBRAL_SIGNIFICATIVO:
        return "SIGNIFICATIVO"
    if psi >= UMBRAL_MODERADO:
        return "MODERADO"
    return "SIN DRIFT"


def analizar_drift(referencia: pd.DataFrame, produccion: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for col in FEATURES_NUMERICAS + FEATURES_CATEGORICAS:
        psi = calcular_psi(referencia[col].astype(float), produccion[col].astype(float))
        filas.append({
            "variable": col,
            "psi": round(psi, 4),
            "clasificacion": clasificar_psi(psi),
            "media_referencia": round(referencia[col].mean(), 3),
            "media_produccion": round(produccion[col].mean(), 3),
        })
    return pd.DataFrame(filas).sort_values("psi", ascending=False).reset_index(drop=True)


def generar_reporte(resultado: pd.DataFrame) -> str:
    lineas = [
        "# Reporte de Data Drift\n",
        f"Comparacion: `{REFERENCIA_PATH}` (entrenamiento) vs "
        f"`{PRODUCCION_PATH}` (produccion simulada).\n",
        "| Variable | PSI | Clasificacion | Media referencia | Media producción |",
        "|---|---|---|---|---|",
    ]
    for _, fila in resultado.iterrows():
        lineas.append(
            f"| {fila['variable']} | {fila['psi']:.4f} | {fila['clasificacion']} | "
            f"{fila['media_referencia']} | {fila['media_produccion']} |"
        )

    n_significativo = (resultado["clasificacion"] == "SIGNIFICATIVO").sum()
    n_moderado = (resultado["clasificacion"] == "MODERADO").sum()
    lineas.append("")
    lineas.append(
        f"**Resumen:** {n_significativo} variable(s) con drift significativo, "
        f"{n_moderado} con drift moderado."
    )
    if n_significativo > 0 or n_moderado > 0:
        lineas.append(
            "\n**Alerta ALERT-DRIFT-01 disparada.** Ver "
            "`actividad8/docs/runbook_drift.md` para el procedimiento de respuesta."
        )
    return "\n".join(lineas)


if __name__ == "__main__":
    referencia = pd.read_csv(REFERENCIA_PATH)
    produccion = pd.read_csv(PRODUCCION_PATH)

    resultado = analizar_drift(referencia, produccion)
    print(resultado.to_string(index=False))

    reporte_md = generar_reporte(resultado)
    REPORTE_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORTE_PATH.write_text(reporte_md, encoding="utf-8")
    print(f"\nReporte escrito en {REPORTE_PATH}")

    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name="deteccion_drift"):
        for _, fila in resultado.iterrows():
            mlflow.log_metric(f"psi_{fila['variable']}", fila["psi"])
        mlflow.log_metric("variables_con_drift_significativo",
                           int((resultado["clasificacion"] == "SIGNIFICATIVO").sum()))
        mlflow.log_metric("variables_con_drift_moderado",
                           int((resultado["clasificacion"] == "MODERADO").sum()))
        mlflow.log_artifact(str(REPORTE_PATH))
        mlflow.log_artifact(str(PRODUCCION_PATH))
