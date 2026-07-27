"""Genera graficas de la prueba de carga a partir de datos ya existentes
(Actividad 9). No ejecuta ninguna peticion nueva contra Render ni local:
solo lee actividad9/evidencia/resultados_prueba_carga.json (generado por
scripts/prueba_carga.py) y produce las visualizaciones.

Paleta y especificaciones de marca segun la skill de dataviz del proyecto:
slot 1 (azul #2a78d6), slot 2 (naranja #eb6834), slot 3 (aqua #1baf7a),
validados con scripts/validate_palette.js (ver commit de esta actividad).

Uso:
    python -m actividad9.scripts.graficar_carga
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt

RESULTADOS_PATH = Path("actividad9/evidencia/resultados_prueba_carga.json")
OUT_DIR = Path("actividad9/evidencia/graficas")

AZUL = "#2a78d6"
NARANJA = "#eb6834"
AQUA = "#1baf7a"
GRIS_TEXTO = "#52514e"
GRIS_GRID = "#d8d7d2"

plt.rcParams.update({
    "font.size": 10,
    "axes.edgecolor": GRIS_GRID,
    "axes.labelcolor": GRIS_TEXTO,
    "text.color": GRIS_TEXTO,
    "xtick.color": GRIS_TEXTO,
    "ytick.color": GRIS_TEXTO,
    "axes.grid": True,
    "grid.color": GRIS_GRID,
    "grid.linewidth": 0.6,
    "axes.spines.top": False,
    "axes.spines.right": False,
})


def cargar_datos() -> dict:
    registros = json.loads(RESULTADOS_PATH.read_text(encoding="utf-8"))
    por_entorno = {"render_prod": {}, "local_docker": {}}
    for r in registros:
        prefijo = "render_prod" if r["run_name"].startswith("render_prod") else "local_docker"
        por_entorno[prefijo][r["concurrencia"]] = r
    return por_entorno


def graficar_throughput(datos: dict) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 3.5))

    for ax, clave, titulo in [(ax1, "render_prod", "Render (producción)"),
                               (ax2, "local_docker", "Local (Docker)")]:
        puntos = datos[clave]
        xs = sorted(puntos)
        ys = [puntos[x]["throughput_req_s"] for x in xs]
        ax.plot(xs, ys, color=AZUL, linewidth=2, marker="o", markersize=8)
        ax.set_title(titulo, fontsize=10, color=GRIS_TEXTO, pad=14)
        ax.set_xlabel("Concurrencia")
        ax.set_xticks(xs)
        ax.set_xlim(min(xs) - 1, max(xs) + 1)
        ax.set_ylabel("Throughput (req/s)")
        ax.set_ylim(0, max(ys) * 1.30)
        for x, y in zip(xs, ys):
            ax.annotate(f"{y:.1f}", (x, y), textcoords="offset points",
                        xytext=(0, 10), ha="center", fontsize=8, color=GRIS_TEXTO)

    fig.suptitle("Throughput vs. concurrencia (escalas independientes: ~22× de diferencia)",
                 fontsize=11, color=GRIS_TEXTO)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(OUT_DIR / "throughput_vs_concurrencia.png", dpi=150)
    plt.close(fig)


def graficar_latencia(datos: dict) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 3.8))

    percentiles = [("latencia_p50_ms", "p50", AZUL), ("latencia_p95_ms", "p95", NARANJA),
                   ("latencia_p99_ms", "p99", AQUA)]

    for ax, clave, titulo in [(ax1, "render_prod", "Render (producción)"),
                               (ax2, "local_docker", "Local (Docker)")]:
        puntos = datos[clave]
        xs = sorted(puntos)
        for campo, etiqueta, color in percentiles:
            ys = [puntos[x][campo] for x in xs]
            ax.plot(xs, ys, color=color, linewidth=2, marker="o", markersize=8, label=etiqueta)
        ax.set_title(titulo, fontsize=10, color=GRIS_TEXTO)
        ax.set_xlabel("Concurrencia")
        ax.set_xticks(xs)
        ax.set_ylabel("Latencia (ms)")
        ax.set_ylim(0, max(puntos[x][campo] for x in xs for campo, _, _ in percentiles) * 1.15)

    handles, labels = ax1.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False,
               fontsize=9, bbox_to_anchor=(0.5, -0.02))

    fig.suptitle("Latencia (p50/p95/p99) vs. concurrencia (escalas independientes: ~10-20× de diferencia)",
                 fontsize=11, color=GRIS_TEXTO)
    fig.tight_layout(rect=(0, 0.06, 1, 0.93))
    fig.savefig(OUT_DIR / "latencia_vs_concurrencia.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    datos = cargar_datos()
    graficar_throughput(datos)
    graficar_latencia(datos)
    print(f"Graficas generadas en {OUT_DIR}/")
