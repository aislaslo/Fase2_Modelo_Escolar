"""Entrenamiento y serializacion del modelo de abandono escolar.

Alineado con ISO/IEC 23053: separa el entrenamiento (offline) del uso del
modelo (inferencia), y persiste el artefacto para su reutilizacion.
"""

from pathlib import Path

import joblib
import mlflow
import mlflow.sklearn
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# --- Configuracion ---------------------------------------------------------
DATA_PATH = Path("data/dataset_abandono.csv")
MODEL_PATH = Path("models/modelo_abandono.joblib")
EXPERIMENT_NAME = "abandono_escolar_actividad6"
TARGET = "abandono"
RANDOM_STATE = 42

# Variables numericas a escalar.
NUM_FEATURES = [
    "promedio_academico",
    "materias_reprobadas",
    "asistencia",
    "distancia_campus",
    "horas_trabajo_semanales",
    "semestre_actual",
]
# Variables ya codificadas como enteros (beca, modalidad). Pasan sin escalar.
PASSTHROUGH_FEATURES = ["condicion_beca", "modalidad"]


def cargar_datos(ruta: Path) -> pd.DataFrame:
    """Carga el dataset de abandono escolar."""
    if not ruta.exists():
        raise FileNotFoundError(
            f"No se encontro el dataset en {ruta}. Ejecute primero src/generate_data.py."
        )
    return pd.read_csv(ruta)


def construir_pipeline() -> Pipeline:
    """Construye el pipeline de preprocesamiento y modelo."""
    preprocesamiento = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), NUM_FEATURES),
            ("passthrough", "passthrough", PASSTHROUGH_FEATURES),
        ]
    )
    modelo = LogisticRegression(max_iter=1000, random_state=RANDOM_STATE)
    return Pipeline(steps=[("prep", preprocesamiento), ("clf", modelo)])


def entrenar() -> None:
    """Entrena, evalua, registra en MLflow y serializa el modelo."""
    datos = cargar_datos(DATA_PATH)
    X = datos[NUM_FEATURES + PASSTHROUGH_FEATURES]
    y = datos[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=RANDOM_STATE
    )

    pipeline = construir_pipeline()

    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name="regresion_logistica_despliegue"):
        pipeline.fit(X_train, y_train)

        y_pred = pipeline.predict(X_test)
        y_proba = pipeline.predict_proba(X_test)[:, 1]

        f1 = f1_score(y_test, y_pred)
        auc = roc_auc_score(y_test, y_proba)
        cv_f1 = cross_val_score(pipeline, X, y, cv=5, scoring="f1")

        mlflow.log_param("modelo", "LogisticRegression")
        mlflow.log_metric("f1_test", f1)
        mlflow.log_metric("auc_roc", auc)
        mlflow.log_metric("f1_cv_media", cv_f1.mean())
        mlflow.log_metric("f1_cv_desv", cv_f1.std())
        mlflow.sklearn.log_model(pipeline, "modelo")

        print(f"F1 prueba: {f1:.4f}")
        print(f"AUC-ROC:   {auc:.4f}")
        print(f"F1 CV:     {cv_f1.mean():.4f} (+/- {cv_f1.std():.4f})")

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)
    print(f"Modelo serializado en {MODEL_PATH}")


if __name__ == "__main__":
    entrenar()
