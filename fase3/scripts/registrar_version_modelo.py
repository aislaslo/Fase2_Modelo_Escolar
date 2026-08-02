"""Registro ligero de versiones de modelo/artefactos (Fase 3 -- MLOps).

Decision de diseno: en vez de operar un servidor de registro de modelos
dedicado (ej. MLflow Model Registry con backend remoto), este proyecto usa
**git como registro de versiones**: cada vez que el pipeline reentrena y
acepta un modelo, se agrega un registro (commit, fecha, metricas, hash de
los artefactos) a fase3/evidencia/model_registry.json, que queda versionado
en el mismo historial de git que el modelo y el codigo que lo produjo.

Es una decision FinOps deliberada (ver actividad9/anexo_tecnico.md seccion
1): este proyecto no tiene el volumen de modelos ni de trafico que
justifique pagar/operar infraestructura de registro dedicada; git ya
provee inmutabilidad, historial y trazabilidad -- los mismos requisitos
centrales de un registro de modelos -- sin costo adicional.

Uso:
    python -m fase3.scripts.registrar_version_modelo --f1 0.8493
"""

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

MODEL_PATH = Path("models/modelo_abandono.joblib")
DATA_PATH = Path("data/dataset_abandono.csv")
REGISTRY_PATH = Path("fase3/evidencia/model_registry.json")
F1_MINIMO = 0.80


def sha256_de(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()[:16]


def commit_actual() -> str:
    resultado = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    )
    return resultado.stdout.strip()


def registrar(f1: float) -> dict:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"No se encontro el modelo en {MODEL_PATH}")
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"No se encontro el dataset en {DATA_PATH}")

    registro = {
        "commit": commit_actual(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "f1_prueba": round(f1, 4),
        "f1_minimo_aceptado": F1_MINIMO,
        "aceptado": f1 >= F1_MINIMO,
        "modelo_sha256_16": sha256_de(MODEL_PATH),
        "dataset_sha256_16": sha256_de(DATA_PATH),
    }

    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    historial = []
    if REGISTRY_PATH.exists():
        historial = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    historial.append(registro)
    REGISTRY_PATH.write_text(json.dumps(historial, indent=2, ensure_ascii=False), encoding="utf-8")

    return registro


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--f1", type=float, required=True, help="F1 de prueba del modelo entrenado")
    args = parser.parse_args()

    registro = registrar(args.f1)
    print(json.dumps(registro, indent=2, ensure_ascii=False))
    print(f"\nRegistro agregado a {REGISTRY_PATH}")
