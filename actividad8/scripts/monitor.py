"""Monitoreo proactivo de la API de prediccion de abandono escolar (Actividad 8).

Ejecuta ciclos periodicos contra un despliegue real (por defecto, la API en
Render), mide disponibilidad, latencia y calidad del modelo mediante
"canary checks" (payloads de referencia con clase esperada conocida), y
registra cada ciclo como una serie de tiempo en MLflow para su visualizacion
como dashboard operativo.

Las reglas de alerta (umbrales, severidad, runbook asociado) se leen de
actividad8/scripts/alertas_config.yaml, para mantener la configuracion de
alertamiento separada del codigo de monitoreo.

Uso:
    python -m actividad8.scripts.monitor --duracion-min 5 --intervalo-seg 15
    python -m actividad8.scripts.monitor --base-url http://localhost:8000 --ciclos 3
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import mlflow
import requests
import yaml

DEFAULT_BASE_URL = "https://fase2-abandono-escolar.onrender.com"
EXPERIMENT_NAME = "actividad8_monitoreo_produccion"
CONFIG_PATH = Path(__file__).parent / "alertas_config.yaml"
LOG_PATH = Path(__file__).parent.parent / "evidencia" / "alertas_log.jsonl"

# Payloads de referencia ("canary checks"): la clase esperada se conoce de
# antemano (ver docs/validacion_pruebas.md), por lo que sirven para detectar
# degradacion del modelo en produccion sin necesitar etiquetas reales.
CANARY_RIESGO_BAJO = {
    "payload": {
        "promedio_academico": 9.5, "materias_reprobadas": 0, "asistencia": 0.99,
        "condicion_beca": 1, "distancia_campus": 1.0, "horas_trabajo_semanales": 0,
        "semestre_actual": 6, "modalidad": 0,
    },
    "clase_esperada": 0,
}
CANARY_RIESGO_ALTO = {
    "payload": {
        "promedio_academico": 5.0, "materias_reprobadas": 5, "asistencia": 0.55,
        "condicion_beca": 0, "distancia_campus": 40.0, "horas_trabajo_semanales": 40,
        "semestre_actual": 2, "modalidad": 1,
    },
    "clase_esperada": 1,
}

REQUEST_TIMEOUT_S = 60  # generoso por el cold start del plan gratuito de Render


def cargar_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def medir_endpoint(metodo: str, url: str, **kwargs) -> tuple[int, float, dict]:
    """Ejecuta una peticion HTTP y devuelve (status_code, latencia_ms, body)."""
    inicio = time.perf_counter()
    try:
        respuesta = requests.request(metodo, url, timeout=REQUEST_TIMEOUT_S, **kwargs)
        latencia_ms = (time.perf_counter() - inicio) * 1000
        try:
            body = respuesta.json()
        except ValueError:
            body = {}
        return respuesta.status_code, latencia_ms, body
    except requests.RequestException as error:
        latencia_ms = (time.perf_counter() - inicio) * 1000
        return 0, latencia_ms, {"error": str(error)}


def ejecutar_ciclo(base_url: str, es_primer_ciclo: bool) -> dict:
    """Ejecuta un ciclo de monitoreo: health check + 2 canary checks."""
    timestamp = datetime.now(timezone.utc).isoformat()

    health_status, health_latency, _ = medir_endpoint("GET", f"{base_url}/health")

    bajo_status, bajo_latencia, bajo_body = medir_endpoint(
        "POST", f"{base_url}/predict", json=CANARY_RIESGO_BAJO["payload"]
    )
    alto_status, alto_latencia, alto_body = medir_endpoint(
        "POST", f"{base_url}/predict", json=CANARY_RIESGO_ALTO["payload"]
    )

    predict_latency_ms = (bajo_latencia + alto_latencia) / 2
    cold_start = es_primer_ciclo and predict_latency_ms > 5000

    clase_bajo = bajo_body.get("clase_predicha")
    clase_alto = alto_body.get("clase_predicha")
    canary_correcto = (
        clase_bajo == CANARY_RIESGO_BAJO["clase_esperada"]
        and clase_alto == CANARY_RIESGO_ALTO["clase_esperada"]
    )

    disponible = health_status == 200 and bajo_status == 200 and alto_status == 200

    return {
        "timestamp": timestamp,
        "health_status_code": health_status,
        "health_latency_ms": round(health_latency, 1),
        "predict_status_code_bajo": bajo_status,
        "predict_status_code_alto": alto_status,
        "predict_latency_ms": round(predict_latency_ms, 1),
        "cold_start": cold_start,
        "clase_predicha_bajo": clase_bajo,
        "clase_predicha_alto": clase_alto,
        "canary_correcto": canary_correcto,
        "disponible": disponible,
        "probabilidad_bajo": bajo_body.get("probabilidad_abandono"),
        "probabilidad_alto": alto_body.get("probabilidad_abandono"),
    }


def evaluar_alertas(ciclo: dict, historial: list[dict], config: dict) -> list[dict]:
    """Compara el ciclo actual (y el historial reciente) contra las reglas de
    alertas_config.yaml y devuelve la lista de alertas disparadas."""
    disparadas = []
    reglas = {r["id"]: r for r in config["alertas"]}

    if not ciclo["disponible"]:
        disparadas.append(reglas["ALERT-AVAIL-01"])

    if not ciclo["canary_correcto"]:
        disparadas.append(reglas["ALERT-QUALITY-01"])

    if ciclo["cold_start"]:
        disparadas.append(reglas["ALERT-LAT-02"])
    else:
        ultimos_3 = (historial + [ciclo])[-3:]
        if len(ultimos_3) == 3 and all(
            c["predict_latency_ms"] > 2000 and not c["cold_start"] for c in ultimos_3
        ):
            disparadas.append(reglas["ALERT-LAT-01"])

    return disparadas


def registrar_alertas(alertas: list[dict], ciclo: dict) -> None:
    """Escribe cada alerta disparada a un log JSONL (evidencia) y a consola,
    ordenadas por severidad para simular priorizacion por impacto operativo."""
    orden_severidad = {"P1": 0, "P2": 1, "P3": 2}
    alertas_ordenadas = sorted(alertas, key=lambda a: orden_severidad[a["severidad"]])

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        for alerta in alertas_ordenadas:
            registro = {
                "timestamp": ciclo["timestamp"],
                "alerta_id": alerta["id"],
                "nombre": alerta["nombre"],
                "severidad": alerta["severidad"],
                "runbook": alerta["accion_runbook"],
                "ciclo": ciclo,
            }
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
            print(
                f"  [{alerta['severidad']}] {alerta['id']} — {alerta['nombre']} "
                f"-> runbook: {alerta['accion_runbook']}"
            )


def monitorear(base_url: str, ciclos: int, intervalo_seg: int, run_name: str | None) -> None:
    config = cargar_config()
    mlflow.set_experiment(EXPERIMENT_NAME)

    historial: list[dict] = []

    with mlflow.start_run(run_name=run_name):
        mlflow.log_param("base_url", base_url)
        mlflow.log_param("ciclos_planeados", ciclos)
        mlflow.log_param("intervalo_seg", intervalo_seg)

        for i in range(ciclos):
            ciclo = ejecutar_ciclo(base_url, es_primer_ciclo=(i == 0))
            print(f"[ciclo {i}] {ciclo['timestamp']} "
                  f"disponible={ciclo['disponible']} "
                  f"latencia_predict={ciclo['predict_latency_ms']}ms "
                  f"canary_ok={ciclo['canary_correcto']}"
                  f"{' (cold start)' if ciclo['cold_start'] else ''}")

            mlflow.log_metrics(
                {
                    "health_latency_ms": ciclo["health_latency_ms"],
                    "predict_latency_ms": ciclo["predict_latency_ms"],
                    "disponible": 1.0 if ciclo["disponible"] else 0.0,
                    "canary_correcto": 1.0 if ciclo["canary_correcto"] else 0.0,
                    "cold_start": 1.0 if ciclo["cold_start"] else 0.0,
                },
                step=i,
            )

            alertas = evaluar_alertas(ciclo, historial, config)
            if alertas:
                registrar_alertas(alertas, ciclo)
                mlflow.log_metric("alertas_disparadas", len(alertas), step=i)
            else:
                mlflow.log_metric("alertas_disparadas", 0, step=i)

            historial.append(ciclo)

            if i < ciclos - 1:
                time.sleep(intervalo_seg)

    print(f"\nMonitoreo finalizado. {len(historial)} ciclos registrados en "
          f"MLflow (experimento '{EXPERIMENT_NAME}'). Log de alertas: {LOG_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--ciclos", type=int, default=5)
    parser.add_argument("--intervalo-seg", type=int, default=10)
    parser.add_argument("--run-name", default=None)
    args = parser.parse_args()

    monitorear(args.base_url, args.ciclos, args.intervalo_seg, args.run_name)
