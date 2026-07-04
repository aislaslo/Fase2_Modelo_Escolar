"""Contrato de entrada y salida de la API mediante Pydantic."""

from enum import IntEnum

from pydantic import BaseModel, Field


class Modalidad(IntEnum):
    """Modalidad de estudio del estudiante."""

    PRESENCIAL = 0
    EN_LINEA = 1


class EstudianteEntrada(BaseModel):
    """Esquema de entrada con las ocho variables predictoras del modelo."""

    promedio_academico: float = Field(
        ..., ge=0.0, le=10.0, description="Promedio de calificaciones (0-10)."
    )
    materias_reprobadas: int = Field(
        ..., ge=0, description="Numero de materias reprobadas."
    )
    asistencia: float = Field(
        ..., ge=0.0, le=1.0, description="Indice de asistencia (0-1)."
    )
    condicion_beca: int = Field(
        ..., ge=0, le=1, description="1 si cuenta con beca, 0 en caso contrario."
    )
    distancia_campus: float = Field(
        ..., ge=0.0, description="Distancia al campus en kilometros."
    )
    horas_trabajo_semanales: int = Field(
        ..., ge=0, le=168, description="Horas de trabajo remunerado por semana."
    )
    semestre_actual: int = Field(
        ..., ge=1, description="Semestre que cursa el estudiante."
    )
    modalidad: Modalidad = Field(..., description="Modalidad de estudio.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "promedio_academico": 7.8,
                "materias_reprobadas": 2,
                "asistencia": 0.82,
                "condicion_beca": 1,
                "distancia_campus": 12.5,
                "horas_trabajo_semanales": 20,
                "semestre_actual": 4,
                "modalidad": 0,
            }
        }
    }


class PrediccionSalida(BaseModel):
    """Esquema de la respuesta del endpoint de prediccion."""

    probabilidad_abandono: float = Field(..., description="Probabilidad estimada (0-1).")
    clase_predicha: int = Field(..., description="0 = continua, 1 = abandona.")
    umbral_aplicado: float = Field(..., description="Umbral de decision utilizado.")
    nivel_riesgo: str = Field(..., description="Categoria cualitativa de riesgo.")
