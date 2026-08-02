"""Pruebas automatizadas de datos (Fase 3 -- pipeline MLOps).

Complementan tests/test_api.py (pruebas de codigo) con validaciones sobre
data/dataset_abandono.csv: que el dataset de entrenamiento cumpla el mismo
contrato de datos que la API expone en produccion (src/schema.py), y que su
forma general (filas, nulos, balance de clases) no se haya corrompido.

Se ejecutan en el pipeline de CI (.github/workflows/pipeline.yml) antes de
reentrenar el modelo -- un dataset invalido no debe llegar a entrenamiento.
"""

from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError

from src.schema import EstudianteEntrada

DATA_PATH = Path("data/dataset_abandono.csv")
COLUMNAS_ESPERADAS = [
    "promedio_academico", "materias_reprobadas", "asistencia", "condicion_beca",
    "distancia_campus", "horas_trabajo_semanales", "semestre_actual", "modalidad",
    "abandono",
]


@pytest.fixture(scope="module")
def datos() -> pd.DataFrame:
    assert DATA_PATH.exists(), f"No se encontro el dataset en {DATA_PATH}"
    return pd.read_csv(DATA_PATH)


def test_columnas_esperadas_presentes(datos: pd.DataFrame):
    faltantes = set(COLUMNAS_ESPERADAS) - set(datos.columns)
    assert not faltantes, f"Columnas faltantes en el dataset: {faltantes}"


def test_sin_valores_nulos(datos: pd.DataFrame):
    nulos = datos[COLUMNAS_ESPERADAS].isnull().sum()
    columnas_con_nulos = nulos[nulos > 0]
    assert columnas_con_nulos.empty, f"Columnas con valores nulos:\n{columnas_con_nulos}"


def test_sin_filas_duplicadas(datos: pd.DataFrame):
    duplicadas = datos.duplicated().sum()
    assert duplicadas == 0, f"{duplicadas} filas duplicadas encontradas"


def test_cantidad_de_registros_razonable(datos: pd.DataFrame):
    # El dataset sintetico de la Fase 2 se genera con 1000 registros; se
    # tolera un rango en caso de que se regenere con otro tamano, pero un
    # dataset casi vacio o extremadamente pequeno indica un problema real.
    assert len(datos) >= 100, f"El dataset tiene muy pocos registros: {len(datos)}"


def test_columna_objetivo_binaria(datos: pd.DataFrame):
    valores = set(datos["abandono"].unique())
    assert valores <= {0, 1}, f"La columna 'abandono' tiene valores fuera de {{0,1}}: {valores}"


def test_balance_de_clases_no_degenerado(datos: pd.DataFrame):
    proporcion = datos["abandono"].mean()
    assert 0.10 <= proporcion <= 0.90, (
        f"Proporcion de 'abandono' fuera de un rango razonable: {proporcion:.3f}. "
        "Un dataset casi todo de una sola clase produce un modelo inutil."
    )


def test_filas_cumplen_el_contrato_de_entrada_de_la_api(datos: pd.DataFrame):
    """Cada fila (sin la columna objetivo) debe validar contra el mismo
    esquema Pydantic (EstudianteEntrada) que la API aplica a las peticiones
    reales -- garantiza que entrenamiento y servicio comparten un unico
    contrato de datos, sin dos definiciones que puedan desincronizarse."""
    columnas_entrada = [c for c in COLUMNAS_ESPERADAS if c != "abandono"]
    errores = []
    for idx, fila in datos[columnas_entrada].iterrows():
        try:
            EstudianteEntrada(**fila.to_dict())
        except ValidationError as error:
            errores.append((idx, str(error)))
            if len(errores) >= 5:
                break

    assert not errores, (
        f"{len(errores)}+ filas no cumplen el esquema EstudianteEntrada. "
        f"Primeros errores: {errores}"
    )
