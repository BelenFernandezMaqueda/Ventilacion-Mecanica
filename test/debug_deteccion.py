"""Traza como cambian las variables de detectar_respiraciones dentro de una
ventana de tiempo, sobre la señal elegida. Copia las dos funciones, les mete
prints (solo cuando algo cambia) y grafica la derivada con shading por estado.

    python test/debug_deteccion.py
"""

import sys
from collections import deque
from pathlib import Path

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from Back.detectar_respiracion import filtrar_pasabajos
from Back.gestor_señales import GestorSeñales

# ------------------------------------------------------------------ elegir ---
ARCHIVO = "Mini TP Signals D.txt"
T_INICIO = 1627.0          # segundos, relativo al comienzo de la señal
T_FIN = 1640.0
SALIDA_PNG = ROOT / "test" / "debug_deteccion.png"
# parametros (los mismos que usa test_tres_metodos.py)
FS = 256
FRECUENCIA_CORTE = 3.0
UMBRAL_POSITIVO = 70000
UMBRAL_NEGATIVO = -70000
TIEMPO_MAXIMO = 4
N_HISTORIAL = 10
FACTOR_UMBRAL = 0.4
MUESTRAS_PICO_NEGATIVO = 200
# ---------------------------------------------------------------------------

# codigos de estado por muestra
FUERA = 0            # respiracion == False
DENTRO_PICO = 1      # respiracion == True  y  adentro_pico_p == True
EN_RESP = 2          # respiracion == True  y  adentro_pico_p == False

COLOR_ESTADO = {
    FUERA: ("#f0f0f0", "fuera de respiracion"),
    DENTRO_PICO: ("#9ecae1", "en respiracion / dentro del pico +"),
    EN_RESP: ("#fdae6b", "en respiracion / fuera del pico +"),
}
COLOR_EVENTO = {
    "abre": ("#1f77b4", "ABRE respiracion", "ABRE"),
    "pico_nuevo": ("#9467bd", "pico + nuevo", "pico+ nuevo"),
    "sale_pico": ("#7f7f7f", "sale del pico +", "sale+"),
    "cierra": ("#d62728", "CIERRA y confirma", "CIERRA"),
    "descarta": ("#8c564b", "cierra pero descarta", "descarta"),
}


def detectar_respiraciones(derivada, tiempo,
                           umbral_positivo=UMBRAL_POSITIVO,
                           umbral_negativo=UMBRAL_NEGATIVO,
                           tiempo_maximo=TIEMPO_MAXIMO,
                           n_historial=N_HISTORIAL,
                           factor_umbral=FACTOR_UMBRAL,
                           muestras_pico_negativo=MUESTRAS_PICO_NEGATIVO):
    derivada = np.asarray(derivada, dtype=float)
    tiempo = np.asarray(tiempo, dtype=float)
    picos_positivos = deque([umbral_positivo] * n_historial, maxlen=n_historial)
    picos_negativos = deque([umbral_negativo] * n_historial, maxlen=n_historial)
    adentro_pico_p = False
    respiracion = False
    indice_inicio = 0
    respiraciones = []

    n = len(derivada)
    estado = np.zeros(n, dtype=int)
    u_pos = np.zeros(n)
    u_neg = np.zeros(n)
    eventos = []          # (indice, tipo)

    for i in range(n):
        umbral_positivo_actual = factor_umbral * sum(picos_positivos) / len(picos_positivos)
        umbral_negativo_actual = factor_umbral * sum(picos_negativos) / len(picos_negativos)
        u_pos[i] = umbral_positivo_actual
        u_neg[i] = umbral_negativo_actual

        if not respiracion and derivada[i] > umbral_positivo_actual:
            respiracion = True
            indice_inicio = i
            adentro_pico_p = True
            eventos.append((i, "abre"))
        elif respiracion and adentro_pico_p and derivada[i] < umbral_positivo_actual:
            adentro_pico_p = False
            eventos.append((i, "sale_pico"))
        elif respiracion and derivada[i] > umbral_positivo_actual and not adentro_pico_p:
            indice_inicio = i
            adentro_pico_p = True
            eventos.append((i, "pico_nuevo"))
        elif respiracion and derivada[i] < umbral_negativo_actual:
            respiracion = False
            dur = tiempo[i] - tiempo[indice_inicio]
            if dur <= tiempo_maximo:
                respiraciones.append(tiempo[indice_inicio])
                picos_positivos.append(derivada[indice_inicio:i + 1].max())
                picos_negativos.append(
                    derivada[indice_inicio:i + muestras_pico_negativo].min()
                )
                eventos.append((i, "cierra"))
            else:
                eventos.append((i, "descarta"))

        if respiracion and adentro_pico_p:
            estado[i] = DENTRO_PICO
        elif respiracion:
            estado[i] = EN_RESP
        else:
            estado[i] = FUERA

    return np.asarray(respiraciones, dtype=float), estado, u_pos, u_neg, eventos


def detectar_respiraciones_filtrado(flujo, tiempo, fs=FS,
                                    frecuencia_corte=FRECUENCIA_CORTE,
                                    umbral_positivo=UMBRAL_POSITIVO,
                                    umbral_negativo=UMBRAL_NEGATIVO,
                                    tiempo_maximo=TIEMPO_MAXIMO):
    flujo = np.asarray(flujo, dtype=float)
    tiempo = np.asarray(tiempo, dtype=float)
    flujo_filtrado = filtrar_pasabajos(flujo, fs, frecuencia_corte=frecuencia_corte)
    derivada_filtrada = np.gradient(flujo_filtrado, tiempo)
    derivada_filtrada = np.sign(derivada_filtrada) * derivada_filtrada ** 2
    resultado = detectar_respiraciones(
        derivada_filtrada, tiempo,
        umbral_positivo=umbral_positivo, umbral_negativo=umbral_negativo,
        tiempo_maximo=tiempo_maximo,
    )
    return (*resultado, derivada_filtrada)


def _tramos(estado):
    """Devuelve (inicio, fin, codigo) de cada tramo contiguo de mismo estado."""
    cambios = np.flatnonzero(np.diff(estado)) + 1
    bordes = np.concatenate([[0], cambios, [len(estado)]])
    return [(bordes[k], bordes[k + 1], estado[bordes[k]])
            for k in range(len(bordes) - 1)]


def imprimir_trazas(tiempo, derivada, estado, u_pos, u_neg, eventos, t0, t1):
    print("\n--- cambios de estado en la ventana ---")
    ultimo = None
    ev_por_i = {}
    for i, tipo in eventos:
        ev_por_i.setdefault(i, []).append(tipo)
    for i in range(len(tiempo)):
        if not (t0 <= tiempo[i] <= t1):
            continue
        clave = (round(u_pos[i], 1), round(u_neg[i], 1), estado[i])
        if clave != ultimo:
            ultimo = clave
            nombre = COLOR_ESTADO[estado[i]][1]
            print(f"t={tiempo[i]:9.4f}  deriv={derivada[i]:+13.1f}  "
                  f"U+={u_pos[i]:+11.1f}  U-={u_neg[i]:+9.1f}  | {nombre}")
        for tipo in ev_por_i.get(i, []):
            print(f"    -> {tipo}  (t={tiempo[i]:.4f}, deriv={derivada[i]:+.1f})")


def _dibujar(ax, t, d, est, u_pos_w, u_neg_w, eventos_w, span):
    # shading por estado
    vistos = set()
    for a, b, cod in _tramos(est):
        color, nombre = COLOR_ESTADO[cod]
        ta, tb = t[a], t[min(b, len(t) - 1)]
        ax.axvspan(ta, tb, color=color,
                   label=None if cod in vistos else nombre, zorder=0)
        vistos.add(cod)
        # flechita si el tramo es muy angosto para verse
        if cod != FUERA and (tb - ta) < span * 0.02:
            xm = (ta + tb) / 2
            y0, y1 = ax.get_ylim()
            ax.annotate(nombre.split("/")[-1].strip(),
                        xy=(xm, 0), xytext=(xm, y0 + (y1 - y0) * 0.78),
                        ha="center", fontsize=8, color=color,
                        arrowprops=dict(arrowstyle="->", color=color, lw=1.6))

    ax.plot(t, d, color="black", linewidth=0.9, zorder=5)
    ax.step(t, u_pos_w, where="post", color="#2ca02c", lw=1, ls="--",
            label="U+ (umbral positivo)")
    ax.step(t, u_neg_w, where="post", color="#d62728", lw=1, ls="--",
            label="U- (umbral negativo)")
    ax.axhline(0, color="#bbbbbb", lw=0.6)

    # eventos: linea vertical + etiqueta escalonada arriba
    vistos_ev = set()
    for k, (te, tipo) in enumerate(eventos_w):
        color, nombre, corto = COLOR_EVENTO[tipo]
        ax.axvline(te, color=color, lw=1.4, alpha=0.9,
                   label=None if tipo in vistos_ev else nombre, zorder=6)
        y0, y1 = ax.get_ylim()
        ypos = y1 - (y1 - y0) * (0.05 + 0.09 * (k % 3))
        ax.annotate(corto, xy=(te, ypos), ha="center", fontsize=7,
                    color=color, fontweight="bold", zorder=7,
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec=color, lw=0.6))
        vistos_ev.add(tipo)

    ax.set_xlim(t[0], t[-1])
    ax.grid(True, alpha=0.2)


def plotear(tiempo, derivada, estado, u_pos, u_neg, eventos, t0, t1, inicio_señal):
    win = (tiempo >= t0) & (tiempo <= t1)
    idx = np.flatnonzero(win)
    i0, i1 = idx[0], idx[-1] + 1
    t = tiempo[i0:i1] - inicio_señal
    d = derivada[i0:i1]
    est = estado[i0:i1]
    span = t[-1] - t[0]
    eventos_w = [(tiempo[i] - inicio_señal, tipo) for i, tipo in eventos if i0 <= i < i1]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 9), sharex=True)

    # panel 1: rango completo
    _dibujar(ax1, t, d, est, u_pos[i0:i1], u_neg[i0:i1], eventos_w, span)
    ax1.set_ylabel("derivada (rango completo)")
    ax1.set_title(f"{ARCHIVO}   ventana {T_INICIO}-{T_FIN} s")
    ax1.legend(loc="lower right", fontsize=8, framealpha=0.9, ncol=2)

    # panel 2: zoom a la zona de los umbrales / picos positivos
    d_pos = d[d > 0]
    lim = 1.4 * max(u_pos[i0:i1].max(), d_pos.max() if d_pos.size else u_pos[i0:i1].max())
    ax2.set_ylim(-lim, lim)
    _dibujar(ax2, t, d, est, u_pos[i0:i1], u_neg[i0:i1], eventos_w, span)
    ax2.set_ylim(-lim, lim)
    ax2.set_ylabel("derivada (zoom a los umbrales)")
    ax2.set_xlabel("tiempo relativo a la señal (s)")

    fig.tight_layout()
    fig.savefig(SALIDA_PNG, dpi=130)
    print(f"\ngrafico guardado en {SALIDA_PNG}")


def main():
    señal = GestorSeñales(ROOT / "datos").cargar(ROOT / "datos" / ARCHIVO)
    t0 = señal.inicio + T_INICIO
    t1 = señal.inicio + T_FIN
    print(f"{ARCHIVO}  |  ventana relativa {T_INICIO}-{T_FIN}s  "
          f"(absoluta {t0:.4f}-{t1:.4f}s)")

    respiraciones, estado, u_pos, u_neg, eventos, derivada = \
        detectar_respiraciones_filtrado(señal.flujo, señal.tiempo, fs=señal.fs)

    imprimir_trazas(señal.tiempo, derivada, estado, u_pos, u_neg, eventos, t0, t1)

    en_ventana = respiraciones[(respiraciones >= t0) & (respiraciones <= t1)]
    print(f"\nrespiraciones detectadas en la ventana (relativo): "
          f"{np.round(en_ventana - señal.inicio, 4).tolist()}")

    plotear(señal.tiempo, derivada, estado, u_pos, u_neg, eventos, t0, t1, señal.inicio)


if __name__ == "__main__":
    main()
