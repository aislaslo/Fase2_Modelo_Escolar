"""Auditoria de fairness (equidad) del modelo de prediccion de abandono
escolar (Actividad 9 -- gobernanza responsable).

El dataset no tiene un atributo demografico explicito (genero, etnia,
discapacidad); se usa `condicion_beca` (con beca vs sin beca) como proxy de
nivel socioeconomico -- el atributo protegido/sensible mas plausible
disponible en las 8 variables predictoras.

Metricas calculadas (definiciones estandar de fairness en ML clasificatorio):
  - Selection rate: proporcion de predicciones "abandono=1" por grupo.
    Compara paridad demografica (demographic parity).
  - TPR (recall) y FPR por grupo: comparan paridad de oportunidad
    (equal opportunity) y odds igualadas (equalized odds).
  - Regla de las cuatro quintas partes (80% rule, EEOC): si el cociente
    entre selection rates de ambos grupos es menor a 0.8, se considera
    evidencia de posible sesgo adverso.

Se evalua sobre el mismo conjunto de prueba (20%, random_state=42, ver
src/train.py) usado para reportar las metricas de la Fase 2, no sobre el
conjunto de entrenamiento, para no inflar artificialmente los resultados.

Uso:
    python -m actividad9.scripts.auditoria_fairness
"""

from pathlib import Path

import joblib
import mlflow
import pandas as pd
from sklearn.model_selection import train_test_split

MODEL_PATH = Path("models/modelo_abandono.joblib")
DATA_PATH = Path("data/dataset_abandono.csv")
REPORTE_PATH = Path("actividad9/evidencia/reporte_fairness.md")
EXPERIMENT_NAME = "actividad9_fairness"

NUM_FEATURES = [
    "promedio_academico", "materias_reprobadas", "asistencia",
    "distancia_campus", "horas_trabajo_semanales", "semestre_actual",
]
PASSTHROUGH_FEATURES = ["condicion_beca", "modalidad"]
TARGET = "abandono"
RANDOM_STATE = 42
UMBRAL_DECISION = 0.40
ATRIBUTO_PROTEGIDO = "condicion_beca"
UMBRAL_4_5 = 0.80  # four-fifths rule (EEOC)


def cargar_test_set() -> tuple[pd.DataFrame, pd.Series]:
    datos = pd.read_csv(DATA_PATH)
    X = datos[NUM_FEATURES + PASSTHROUGH_FEATURES]
    y = datos[TARGET]
    _, X_test, _, y_test = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=RANDOM_STATE
    )
    return X_test, y_test


def metricas_por_grupo(y_real: pd.Series, y_pred: pd.Series) -> dict:
    tp = int(((y_pred == 1) & (y_real == 1)).sum())
    fp = int(((y_pred == 1) & (y_real == 0)).sum())
    fn = int(((y_pred == 0) & (y_real == 1)).sum())
    tn = int(((y_pred == 0) & (y_real == 0)).sum())
    n = len(y_real)

    selection_rate = (tp + fp) / n if n else 0.0
    tpr = tp / (tp + fn) if (tp + fn) else 0.0  # recall / equal opportunity
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    accuracy = (tp + tn) / n if n else 0.0

    return {
        "n": n, "selection_rate": round(selection_rate, 4),
        "tpr_recall": round(tpr, 4), "fpr": round(fpr, 4),
        "precision": round(precision, 4), "accuracy": round(accuracy, 4),
    }


def auditar() -> dict:
    modelo = joblib.load(MODEL_PATH)
    X_test, y_test = cargar_test_set()

    proba = modelo.predict_proba(X_test)[:, 1]
    y_pred = pd.Series((proba >= UMBRAL_DECISION).astype(int), index=X_test.index)

    grupos = {}
    for valor_grupo, nombre in [(0, "sin_beca"), (1, "con_beca")]:
        mascara = X_test[ATRIBUTO_PROTEGIDO] == valor_grupo
        grupos[nombre] = metricas_por_grupo(y_test[mascara], y_pred[mascara])

    sr_sin = grupos["sin_beca"]["selection_rate"]
    sr_con = grupos["con_beca"]["selection_rate"]
    cociente_4_5 = min(sr_sin, sr_con) / max(sr_sin, sr_con) if max(sr_sin, sr_con) > 0 else 1.0

    demographic_parity_diff = round(abs(sr_sin - sr_con), 4)
    equal_opportunity_diff = round(abs(grupos["sin_beca"]["tpr_recall"] - grupos["con_beca"]["tpr_recall"]), 4)
    fpr_diff = round(abs(grupos["sin_beca"]["fpr"] - grupos["con_beca"]["fpr"]), 4)
    equalized_odds_diff = round(max(equal_opportunity_diff, fpr_diff), 4)

    resultado = {
        "atributo_protegido": ATRIBUTO_PROTEGIDO,
        "grupos": grupos,
        "demographic_parity_diff": demographic_parity_diff,
        "equal_opportunity_diff": equal_opportunity_diff,
        "equalized_odds_diff": equalized_odds_diff,
        "cociente_4_5_reglas": round(cociente_4_5, 4),
        "pasa_regla_4_5": cociente_4_5 >= UMBRAL_4_5,
    }
    return resultado


def generar_reporte(resultado: dict) -> str:
    g = resultado["grupos"]
    lineas = [
        "# Reporte de Auditoría de Fairness — Actividad 9\n",
        f"Atributo protegido (proxy socioeconómico): **`{resultado['atributo_protegido']}`** "
        "(0 = sin beca, 1 = con beca). Evaluado sobre el conjunto de prueba "
        "(20%, `random_state=42`), no sobre datos de entrenamiento.\n",
        "## Métricas por grupo\n",
        "| Grupo | n | Selection rate | TPR (recall) | FPR | Precision | Accuracy |",
        "|---|---|---|---|---|---|---|",
        f"| Sin beca | {g['sin_beca']['n']} | {g['sin_beca']['selection_rate']} | "
        f"{g['sin_beca']['tpr_recall']} | {g['sin_beca']['fpr']} | "
        f"{g['sin_beca']['precision']} | {g['sin_beca']['accuracy']} |",
        f"| Con beca | {g['con_beca']['n']} | {g['con_beca']['selection_rate']} | "
        f"{g['con_beca']['tpr_recall']} | {g['con_beca']['fpr']} | "
        f"{g['con_beca']['precision']} | {g['con_beca']['accuracy']} |",
        "",
        "## Métricas de disparidad\n",
        "| Métrica | Valor | Interpretación |",
        "|---|---|---|",
        f"| Demographic parity difference | {resultado['demographic_parity_diff']} | "
        "Diferencia en tasa de predicción de riesgo entre grupos (0 = paridad perfecta) |",
        f"| Equal opportunity difference | {resultado['equal_opportunity_diff']} | "
        "Diferencia en TPR (recall) entre grupos |",
        f"| Equalized odds difference | {resultado['equalized_odds_diff']} | "
        "Máximo entre diferencia de TPR y de FPR |",
        f"| Cociente regla de las 4/5 (EEOC) | {resultado['cociente_4_5_reglas']} | "
        f"{'Cumple' if resultado['pasa_regla_4_5'] else 'NO cumple'} (umbral ≥ 0.80) |",
    ]
    return "\n".join(lineas)


if __name__ == "__main__":
    resultado = auditar()
    print(f"Grupo sin beca: {resultado['grupos']['sin_beca']}")
    print(f"Grupo con beca: {resultado['grupos']['con_beca']}")
    print(f"Demographic parity diff: {resultado['demographic_parity_diff']}")
    print(f"Equal opportunity diff:  {resultado['equal_opportunity_diff']}")
    print(f"Equalized odds diff:     {resultado['equalized_odds_diff']}")
    print(f"Regla 4/5: cociente={resultado['cociente_4_5_reglas']} "
          f"({'CUMPLE' if resultado['pasa_regla_4_5'] else 'NO CUMPLE'})")

    reporte = generar_reporte(resultado)
    REPORTE_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORTE_PATH.write_text(reporte, encoding="utf-8")
    print(f"\nReporte escrito en {REPORTE_PATH}")

    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name="auditoria_fairness_condicion_beca"):
        mlflow.log_metric("demographic_parity_diff", resultado["demographic_parity_diff"])
        mlflow.log_metric("equal_opportunity_diff", resultado["equal_opportunity_diff"])
        mlflow.log_metric("equalized_odds_diff", resultado["equalized_odds_diff"])
        mlflow.log_metric("cociente_4_5_reglas", resultado["cociente_4_5_reglas"])
        mlflow.log_metric("pasa_regla_4_5", int(resultado["pasa_regla_4_5"]))
        mlflow.log_artifact(str(REPORTE_PATH))
