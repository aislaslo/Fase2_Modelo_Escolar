# Manual de Despliegue — API de Predicción de Abandono Escolar

> Cubre: ejecución local, contenerización con Docker y despliegue en la nube bajo el
> modelo PaaS, conforme al Tema 16 (Módulo 2, Semana 8) del curso. El despliegue en la
> nube se **ejecutó realmente** sobre Render; la API pública está disponible en:
>
> **https://fase2-abandono-escolar.onrender.com** (documentación interactiva en
> [`/docs`](https://fase2-abandono-escolar.onrender.com/docs)).

---

## 1. Requerimientos técnicos

| Componente | Requisito |
|------------|-----------|
| Lenguaje | Python 3.11 o superior |
| Gestor de paquetes | pip (ver `requirements.txt`) |
| Contenedores | Docker Engine / Docker Desktop |
| Control de versiones | Git, repositorio en GitHub |
| Cuenta en plataforma PaaS | Render (o equivalente: Railway, Fly.io) |
| Puerto expuesto por el servicio | 8000 en local; `$PORT` (asignado por Render) en la nube |

## 2. Ejecución local sin Docker

```bash
python3.11 -m venv .venv
source .venv/bin/activate          # En Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 1. Generar el dataset (no se dispuso del CSV original de la Actividad 6;
#    ver docs/documentacion_tecnica.md, seccion 2, para la justificacion).
python -m src.generate_data

# 2. Entrenar y serializar el modelo
python -m src.train

# 3. Levantar la API
uvicorn src.api:app --reload
```

La documentación interactiva queda disponible en `http://localhost:8000/docs`
(Swagger UI, generada automáticamente por FastAPI).

## 3. Contenerización con Docker

### 3.1 Construcción de la imagen

```bash
docker build -t abandono-escolar-api .
```

El `Dockerfile` usa `python:3.11-slim` como base, instala dependencias en una capa
separada (aprovecha la caché de Docker) y copia únicamente `src/` y `models/`: el
artefacto del modelo se incluye en la imagen de forma intencional para que el
contenedor sea autosuficiente y no dependa de generar/entrenar el modelo en tiempo de
arranque.

### 3.2 Ejecución del contenedor

```bash
docker run -d -p 8000:8000 --name abandono-escolar-api abandono-escolar-api
```

### 3.3 Verificación

```bash
curl http://localhost:8000/health
# {"estado":"operativo"}

curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"promedio_academico": 7.8, "materias_reprobadas": 2, "asistencia": 0.82,
       "condicion_beca": 1, "distancia_campus": 12.5, "horas_trabajo_semanales": 20,
       "semestre_actual": 4, "modalidad": 0}'
```

Evidencia real de esta verificación (build, ejecución y respuesta de endpoints) se
documenta en [`docs/validacion_pruebas.md`](./validacion_pruebas.md).

## 4. Despliegue en la nube (PaaS)

Se eligió **Render** como plataforma: modelo de servicio **PaaS** (coherente con el
enfoque del Tema 16), soporta despliegue directo desde un `Dockerfile` en un
repositorio de GitHub, ofrece un plan gratuito suficiente para este proyecto y no
requiere gestión manual de infraestructura subyacente. El despliegue se ejecutó
realmente sobre este servicio (no es solo un procedimiento documentado).

### 4.1 Pasos de despliegue (ejecutados)

1. Publicar el repositorio (código fuente, `Dockerfile`, `models/modelo_abandono.joblib`)
   en GitHub — ver sección 5.
2. Crear cuenta en Render con **Sign up with GitHub** y autorizar acceso al repositorio.
3. En Render, **New +** → **Web Service** → seleccionar el repositorio
   `aislaslo/Fase2_Modelo_Escolar`.
4. Render detectó automáticamente **Docker** como entorno de ejecución (por la
   presencia del `Dockerfile` en la raíz del repo); no fue necesario configurarlo
   manualmente.
5. Configuración del servicio: rama `main`, root directory vacío, instance type
   **Free**, sin variables de entorno adicionales (Render inyecta `PORT`
   automáticamente).
6. Ajuste de código necesario antes del despliegue: el `CMD` del `Dockerfile` tenía el
   puerto fijo en 8000. Se cambió a
   `CMD ["sh", "-c", "uvicorn src.api:app --host 0.0.0.0 --port ${PORT:-8000}"]` para
   leer el puerto que Render asigna dinámicamente vía la variable de entorno `PORT`,
   manteniendo el valor 8000 como default para ejecución local. Verificado localmente
   con `docker run -e PORT=10000 ...` antes de subir el cambio.
7. Click en **Deploy web service**: Render construyó la imagen a partir del
   `Dockerfile` (mismo proceso que en local, ver sección 3.1) y la desplegó.
8. Verificación de disponibilidad: el log de despliegue confirmó
   `Uvicorn running on http://0.0.0.0:10000` (puerto asignado por Render) y el mensaje
   `Your service is live`, con la URL pública
   `https://fase2-abandono-escolar.onrender.com`.
9. Se repitieron las pruebas funcionales de la sección 3.3 contra la URL pública (ver
   evidencia en [`docs/validacion_pruebas.md`](./validacion_pruebas.md), sección 6).

### 4.2 Consideraciones de escalabilidad y seguridad (Tema 16)

- **Modelo de servicio:** PaaS — Render gestiona la infraestructura subyacente
  (cómputo, red, balanceo); el equipo del proyecto solo gestiona la imagen y el código.
- **Modelo de infraestructura:** nube pública. Adecuado aquí porque el dataset es
  sintético y no contiene información real de estudiantes; si se usara el dataset real
  de la Actividad 6 con datos institucionales sensibles, correspondería evaluar una
  nube privada o híbrida para el almacenamiento de datos, aun si la API de inferencia
  se mantiene en PaaS público.
- **Escalabilidad:** Render permite escalar horizontalmente el servicio (más
  instancias) sin cambios en el código, dado que la API es *stateless*.
- **Seguridad mínima recomendada antes de usar esto con datos reales de estudiantes:**
  restringir CORS a los orígenes del frontend institucional, y añadir autenticación
  (API key o JWT) en `/predict`, ya que la versión actualmente desplegada no implementa
  control de acceso (aceptable para esta entrega, que usa datos sintéticos).

### 4.3 Alternativas consideradas

- **Railway:** mismo modelo de despliegue por `Dockerfile`, interfaz similar a Render;
  válida como alternativa si Render no estuviera disponible.
- **AWS:** explícitamente no es un requisito según el material del curso; se descarta
  para mantener el despliegue de bajo costo y sin necesidad de gestionar IAM, VPC, etc.

## 5. Publicación del repositorio en GitHub

```bash
git init                                   # si el repo no esta inicializado
git remote add origin <URL-del-repositorio>
git add .
git commit -m "Fase 2: API contenerizada de prediccion de abandono escolar"
git push -u origin main
```

El repositorio debe incluir: código fuente (`src/`), `Dockerfile`, `.dockerignore`,
`requirements.txt`, pruebas (`tests/`), documentación (`docs/`) y `README.md`. Se
excluyen del control de versiones el entorno virtual, el caché de pytest y los datos de
seguimiento local de MLflow (ver `.gitignore`).

## 6. Uso de herramientas de documentación (IA generativa)

Este manual, la documentación técnica ISO/IEC 23053 y el documento de validación se
redactaron con apoyo de **Claude Code** (Anthropic) como asistente de código en VS Code,
siguiendo el enfoque sugerido en el Tema 16 de usar IA generativa para estructurar la
documentación técnica del despliegue. Cada fase (dataset, entrenamiento, API,
contenerización, pruebas, despliegue en Render) fue ejecutada y verificada —local o en
la nube, según corresponda— antes de documentarse.
