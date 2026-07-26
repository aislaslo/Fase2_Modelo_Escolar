"""Prueba de carga moderada para medir throughput, latencia y tasa de error
(Actividad 9 -- analisis de escalabilidad y desempeno).

Envia peticiones concurrentes a /predict usando un pool de hilos, con
concurrencia baja/moderada a proposito (no es una prueba de estres): el
objetivo es caracterizar el comportamiento actual, no tumbar el servicio.

Uso:
    python -m actividad9.scripts.prueba_carga --base-url https://fase2-abandono-escolar.onrender.com --concurrencia 5 --total 30 --run-name render_prod
    python -m actividad9.scripts.prueba_carga --base-url http://localhost:8000 --concurrencia 5 --total 30 --run-name local_docker
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import mlflow
import requests

DEFAULT_BASE_URL = "https://fase2-abandono-escolar.onrender.com"
EXPERIMENT_NAME = "actividad9_prueba_carga"
RESULTADOS_PATH = Path("actividad9/evidencia/resultados_prueba_carga.json")

PAYLOAD = {
    "promedio_academico": 7.8, "materias_reprobadas": 2, "asistencia": 0.82,
    "condicion_beca": 1, "distancia_campus": 12.5, "horas_trabajo_semanales": 20,
    "semestre_actual": 4, "modalidad": 0,
}

REQUEST_TIMEOUT_S = 60


def _una_peticion(base_url: str) -> dict:
    inicio = time.perf_counter()
    try:
        r = requests.post(f"{base_url}/predict", json=PAYLOAD, timeout=REQUEST_TIMEOUT_S)
        latencia_ms = (time.perf_counter() - inicio) * 1000
        return {"ok": r.status_code == 200, "status_code": r.status_code, "latencia_ms": latencia_ms}
    except requests.RequestException as error:
        latencia_ms = (time.perf_counter() - inicio) * 1000
        return {"ok": False, "status_code": 0, "latencia_ms": latencia_ms, "error": str(error)}


def ejecutar_prueba(base_url: str, concurrencia: int, total: int) -> dict:
    print(f"Prueba de carga: {total} peticiones, concurrencia={concurrencia}, contra {base_url}")

    inicio_total = time.perf_counter()
    resultados = []
    with ThreadPoolExecutor(max_workers=concurrencia) as pool:
        futuros = [pool.submit(_una_peticion, base_url) for _ in range(total)]
        for futuro in as_completed(futuros):
            resultados.append(futuro.result())
    duracion_total_s = time.perf_counter() - inicio_total

    latencias = sorted(r["latencia_ms"] for r in resultados)
    exitosas = [r for r in resultados if r["ok"]]
    fallidas = [r for r in resultados if not r["ok"]]

    def percentil(datos: list[float], p: float) -> float:
        if not datos:
            return 0.0
        k = (len(datos) - 1) * p
        f, c = int(k), min(int(k) + 1, len(datos) - 1)
        return datos[f] + (datos[c] - datos[f]) * (k - f)

    resumen = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "concurrencia": concurrencia,
        "total_peticiones": total,
        "exitosas": len(exitosas),
        "fallidas": len(fallidas),
        "tasa_error": round(len(fallidas) / total, 4),
        "duracion_total_s": round(duracion_total_s, 3),
        "throughput_req_s": round(len(exitosas) / duracion_total_s, 3),
        "latencia_p50_ms": round(percentil(latencias, 0.50), 1),
        "latencia_p95_ms": round(percentil(latencias, 0.95), 1),
        "latencia_p99_ms": round(percentil(latencias, 0.99), 1),
        "latencia_min_ms": round(min(latencias), 1) if latencias else 0,
        "latencia_max_ms": round(max(latencias), 1) if latencias else 0,
    }
    return resumen


def guardar_y_registrar(resumen: dict, run_name: str) -> None:
    RESULTADOS_PATH.parent.mkdir(parents=True, exist_ok=True)
    historial = []
    if RESULTADOS_PATH.exists():
        historial = json.loads(RESULTADOS_PATH.read_text(encoding="utf-8"))
    historial.append({"run_name": run_name, **resumen})
    RESULTADOS_PATH.write_text(json.dumps(historial, indent=2, ensure_ascii=False), encoding="utf-8")

    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name=run_name):
        mlflow.log_params({
            "base_url": resumen["base_url"],
            "concurrencia": resumen["concurrencia"],
            "total_peticiones": resumen["total_peticiones"],
        })
        mlflow.log_metrics({
            k: v for k, v in resumen.items()
            if isinstance(v, (int, float)) and k not in ("concurrencia", "total_peticiones")
        })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--concurrencia", type=int, default=5)
    parser.add_argument("--total", type=int, default=30)
    parser.add_argument("--run-name", default="prueba_carga")
    args = parser.parse_args()

    resumen = ejecutar_prueba(args.base_url, args.concurrencia, args.total)
    print(json.dumps(resumen, indent=2, ensure_ascii=False))
    guardar_y_registrar(resumen, args.run_name)
    print(f"\nResultado guardado en {RESULTADOS_PATH}")
