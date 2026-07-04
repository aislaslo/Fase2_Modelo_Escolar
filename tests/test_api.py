"""Pruebas funcionales y de casos extremos de la API."""

from pathlib import Path

from fastapi.testclient import TestClient

from src import inference
from src.api import app

client = TestClient(app)

PAYLOAD_RIESGO_ALTO = {
    "promedio_academico": 5.5,
    "materias_reprobadas": 4,
    "asistencia": 0.60,
    "condicion_beca": 0,
    "distancia_campus": 30.0,
    "horas_trabajo_semanales": 35,
    "semestre_actual": 2,
    "modalidad": 1,
}

PAYLOAD_RIESGO_BAJO = {
    "promedio_academico": 9.2,
    "materias_reprobadas": 0,
    "asistencia": 0.98,
    "condicion_beca": 1,
    "distancia_campus": 2.0,
    "horas_trabajo_semanales": 0,
    "semestre_actual": 6,
    "modalidad": 0,
}


def test_health():
    respuesta = client.get("/health")
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "operativo"


def test_predict_riesgo_alto():
    respuesta = client.post("/predict", json=PAYLOAD_RIESGO_ALTO)
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert 0.0 <= cuerpo["probabilidad_abandono"] <= 1.0
    assert cuerpo["clase_predicha"] == 1
    assert cuerpo["umbral_aplicado"] == 0.40
    assert cuerpo["nivel_riesgo"] == "alto"


def test_predict_riesgo_bajo():
    respuesta = client.post("/predict", json=PAYLOAD_RIESGO_BAJO)
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["clase_predicha"] == 0
    assert cuerpo["nivel_riesgo"] == "bajo"


def test_predict_entrada_incompleta():
    payload = {"promedio_academico": 7.0}  # faltan 7 campos requeridos
    respuesta = client.post("/predict", json=payload)
    assert respuesta.status_code == 422


def test_predict_promedio_fuera_de_rango():
    payload = {**PAYLOAD_RIESGO_ALTO, "promedio_academico": 15.0}  # > 10.0
    respuesta = client.post("/predict", json=payload)
    assert respuesta.status_code == 422


def test_predict_asistencia_negativa():
    payload = {**PAYLOAD_RIESGO_ALTO, "asistencia": -0.1}  # < 0.0
    respuesta = client.post("/predict", json=payload)
    assert respuesta.status_code == 422


def test_predict_materias_reprobadas_negativas():
    payload = {**PAYLOAD_RIESGO_ALTO, "materias_reprobadas": -1}  # < 0
    respuesta = client.post("/predict", json=payload)
    assert respuesta.status_code == 422


def test_predict_modalidad_invalida():
    payload = {**PAYLOAD_RIESGO_ALTO, "modalidad": 9}  # fuera del enum (0 o 1)
    respuesta = client.post("/predict", json=payload)
    assert respuesta.status_code == 422


def test_predict_boundary_asistencia_extremos():
    payload_min = {**PAYLOAD_RIESGO_ALTO, "asistencia": 0.0}
    payload_max = {**PAYLOAD_RIESGO_BAJO, "asistencia": 1.0}
    assert client.post("/predict", json=payload_min).status_code == 200
    assert client.post("/predict", json=payload_max).status_code == 200


def test_predict_horas_trabajo_fuera_de_rango():
    payload = {**PAYLOAD_RIESGO_ALTO, "horas_trabajo_semanales": 200}  # > 168
    respuesta = client.post("/predict", json=payload)
    assert respuesta.status_code == 422


def test_predict_modelo_no_disponible(monkeypatch):
    """Si el artefacto no existe, /predict debe responder 503, no un crash."""
    inference.cargar_modelo.cache_clear()
    monkeypatch.setattr(inference, "MODEL_PATH", Path("models/no_existe.joblib"))

    respuesta = client.post("/predict", json=PAYLOAD_RIESGO_ALTO)

    assert respuesta.status_code == 503
    inference.cargar_modelo.cache_clear()
