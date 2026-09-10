import sys
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from Back.detectar_respiracion import detectar_respiraciones
from Back.gestor_señales import GestorSeñales


DURACION_MAXIMA_ENTRE_PICOS = 2
UMBRAL_POSITIVO = 500
UMBRAL_NEGATIVO = -500


def graficar_respiraciones():
    gestor = GestorSeñales(ROOT / "datos")
    archivos = gestor.archivos_disponibles()

    figura, ejes = plt.subplots(
        len(archivos),
        2,
        figsize=(14, 12),
        sharex=False,
        constrained_layout=True,
    )

    for fila, archivo in zip(ejes, archivos):
        eje_flow, eje_derivada = fila
        señal = gestor.cargar(archivo)
        tiempos_detectados = detectar_respiraciones(
            señal.Fderiv,
            señal.tiempo,
            umbral_positivo=UMBRAL_POSITIVO,
            umbral_negativo=UMBRAL_NEGATIVO,
            tiempo_maximo=DURACION_MAXIMA_ENTRE_PICOS,
        )

        tiempo_relativo = señal.tiempo - señal.inicio
        tiempos_relativos_detectados = tiempos_detectados - señal.inicio
        print(
            f"{archivo.name}: "
            f"{len(tiempos_relativos_detectados)} respiraciones detectadas"
        )

        eje_flow.plot(
            tiempo_relativo,
            señal.flujo,
            color="#1479a8",
            linewidth=0.6,
            label="Flow",
        )
        eje_derivada.plot(
            tiempo_relativo,
            señal.Fderiv,
            color="#d26a2e",
            linewidth=0.6,
            label="Fderiv",
        )

        for numero, tiempo_respiracion in enumerate(
            tiempos_relativos_detectados,
            start=1,
        ):
            estilo_linea = {
                "color": "#d62728",
                "linestyle": "--",
                "linewidth": 0.8,
                "alpha": 0.8,
                "label": "Respiración" if numero == 1 else None,
            }
            eje_flow.axvline(tiempo_respiracion, **estilo_linea)
            eje_derivada.axvline(
                tiempo_respiracion,
                **estilo_linea,
            )

        eje_flow.set_title(
            f"{archivo.name} | Respiraciones detectadas: "
            f"{len(tiempos_relativos_detectados)}"
        )
        eje_flow.set_ylabel("Flow")
        eje_flow.grid(alpha=0.25)
        eje_flow.legend(loc="upper right")

        eje_derivada.set_title("Derivada del flujo")
        eje_derivada.set_ylabel("Fderiv")
        eje_derivada.grid(alpha=0.25)
        eje_derivada.legend(loc="upper right")

    ejes[-1, 0].set_xlabel("Tiempo relativo (s)")
    ejes[-1, 1].set_xlabel("Tiempo relativo (s)")
    figura.suptitle("Detección de respiraciones a partir de Fderiv")
    plt.show()


if __name__ == "__main__":
    graficar_respiraciones()
