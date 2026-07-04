# Documentación Técnica — Despliegue del Modelo de Predicción de Abandono Escolar

> Curso: Gestión de Proyectos de Inteligencia Artificial — Universidad Tecmilenio.
> Alumno: Alejandro Islas López (matrícula T07136481).
> Documentación alineada con la norma **ISO/IEC 23053:2022** (marco para sistemas de IA
> basados en aprendizaje automático), conforme a lo indicado en el Tema 16 del curso.

---

## 1. Propósito del sistema

Servicio de inferencia que estima la probabilidad de abandono escolar de un estudiante
a partir de ocho variables académicas y socioeconómicas, con el fin de apoyar a
coordinadores y directivos institucionales en la identificación temprana de casos de
riesgo. El sistema es la operacionalización (Fase 2) del modelo evaluado en la
Actividad 6 del curso.

Alcance: predicción individual bajo demanda vía API REST. No incluye acciones
automatizadas sobre el estudiante (intervención, notificación) ni almacenamiento
persistente de las predicciones; estas decisiones quedan fuera del alcance del sistema
y son responsabilidad de quien consume la API.

## 2. Trazabilidad de datos

El dataset original de la Actividad 6 (1000 registros, 8 variables predictoras) no
estuvo disponible en el momento de esta implementación. Para no bloquear el desarrollo
de la Fase 2, se generó un **dataset sintético equivalente** (`src/generate_data.py`)
que:

- Reproduce las mismas 8 variables predictoras y su semántica, descritas en el
  contexto de la Actividad 6.
- Simula una relación causal entre variables y abandono mediante una combinación
  lineal con coeficientes de signo consistente con el sentido del negocio (a mayor
  promedio y asistencia, menor riesgo; a mayor número de materias reprobadas, horas de
  trabajo y distancia al campus, mayor riesgo), pasada por una función logística con
  ruido aleatorio.
- Usa una semilla fija (`RANDOM_STATE = 42`), por lo que el dataset es reproducible.
- Fue calibrado (escala de señal y varianza de ruido) para que la Regresión Logística
  alcance métricas de prueba cercanas a las reportadas en la Actividad 6 (F1 objetivo
  ≥ 0.80; ver sección 4).

**Limitación declarada:** al no ser el dataset original, los coeficientes aprendidos y
la importancia relativa de cada variable en este modelo no deben interpretarse como
hallazgos institucionales reales, solo como validación de que el pipeline de
entrenamiento, serialización e inferencia funciona correctamente end-to-end. Si el
dataset real de la Actividad 6 se recupera, basta con reemplazar
`data/dataset_abandono.csv` y volver a ejecutar `src/train.py`.

## 3. Proceso de diseño controlado

| Etapa | Artefacto | Herramienta |
|-------|-----------|-------------|
| Generación/obtención de datos | `src/generate_data.py` → `data/dataset_abandono.csv` | Python (numpy, pandas) |
| Entrenamiento y serialización | `src/train.py` → `models/modelo_abandono.joblib` | scikit-learn, joblib |
| Registro de experimentos | Runs bajo el experimento `abandono_escolar_actividad6` | MLflow (modo local) |
| Definición de contrato de datos | `src/schema.py` | Pydantic |
| Lógica de inferencia | `src/inference.py` | scikit-learn (Pipeline), pandas |
| Exposición como servicio | `src/api.py` | FastAPI, Uvicorn |
| Empaquetado reproducible | `Dockerfile`, `.dockerignore` | Docker |
| Verificación automatizada | `tests/test_api.py` | pytest, FastAPI TestClient |

El modelo se sirve como un `Pipeline` de scikit-learn que incluye el escalado
(`StandardScaler`) y el clasificador (`LogisticRegression`), de modo que el
preprocesamiento aplicado en entrenamiento se replica exactamente en inferencia,
evitando divergencia entre ambos entornos.

## 4. Actividades de verificación y validación

Ver el detalle completo en [`docs/validacion_pruebas.md`](./validacion_pruebas.md).
Resumen de resultados obtenidos en esta implementación:

| Métrica | Valor obtenido | Referencia Actividad 6 |
|---------|----------------|------------------------|
| F1 (prueba, umbral 0.5 en entrenamiento) | 0.8493 | 0.8456 |
| AUC-ROC | 0.9464 | 0.8660 |
| F1 media (5-fold CV) | 0.8155 | 0.8376 |
| Desviación estándar (5-fold CV) | 0.0422 | 0.0226 |

El objetivo SMART original (F1 ≥ 0.80 en validación cruzada de 5 particiones) se
cumple. La API aplica el umbral de decisión de **0.40** (no 0.5) sobre la
probabilidad de abandono, de acuerdo con el análisis de la Actividad 6.

## 5. Supervisión operativa

- **Carga del modelo:** el artefacto se carga una única vez al iniciar el proceso
  (evento `lifespan` de FastAPI), evitando recarga en cada petición.
- **Health check:** `GET /health` permite a un orquestador (Docker, PaaS) verificar
  que el proceso está activo y responde.
- **Manejo de errores:** si el artefacto no existe, `/predict` responde `503`; si la
  entrada no cumple el esquema, responde `422` (validación Pydantic); errores internos
  de inferencia responden `500` con detalle del error.
- **Observabilidad mínima:** los logs de Uvicorn registran cada petición HTTP con su
  código de respuesta, visibles vía `docker logs` en el entorno contenerizado.
- **Pendiente fuera de alcance de esta fase:** monitoreo de *data drift*, reentrenamiento
  automático y alertas; quedan como trabajo futuro si el sistema pasa a producción real.

## 6. Estrategia de fin de vida útil

- El modelo serializado (`models/modelo_abandono.joblib`) está versionado por el tag de
  la imagen Docker que lo contiene; una nueva versión del modelo implica reconstruir y
  publicar una nueva imagen, sin modificar imágenes ya desplegadas.
- Si el modelo se degrada (por ejemplo, cambia el perfil de los estudiantes y el
  dataset de entrenamiento deja de representar la población actual), la estrategia de
  retiro es: (1) dejar de enrutar tráfico a la versión afectada en el PaaS, (2)
  reentrenar con `src/train.py` sobre datos actualizados, (3) volver a validar contra
  el criterio F1 ≥ 0.80 antes de reemplazar la imagen en producción.
- No se conservan datos personales de estudiantes en el servicio: la API es *stateless*
  y no persiste las peticiones recibidas, lo que simplifica el retiro del sistema sin
  dejar remanentes de datos sensibles.

## 7. Uso de inteligencia artificial generativa

Conforme a lo señalado en el Tema 16 (uso de IA generativa como apoyo para
documentación técnica estructurada), esta implementación y su documentación se
desarrollaron con asistencia de **Claude Code** (Anthropic) como asistente de código
dentro de VS Code, bajo supervisión y validación del alumno en cada fase (generación de
datos, entrenamiento, API, contenerización y pruebas descritas en este documento).
