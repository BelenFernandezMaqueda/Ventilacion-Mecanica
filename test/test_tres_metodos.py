"""Visor interactivo para comparar dos metodos de deteccion de respiraciones.

Mismo manejo que ``Front/main.py`` (selector de archivo, navegacion por la
senal, "mostrar todo") pero con un selector de metodo. Los graficos de volumen
y de derivada son solo para testear, por eso viven en este visor aparte y no en
la app principal.

    Metodo 1 (volumen):   Flow | Volumen
    Metodo 2 (filtrado):  Flow | Volumen | dFlow/dt filtrada
"""

import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from Back.detectar_respiracion import (
    detectar_respiraciones_filtrado,
    detectar_respiraciones_por_volumen,
)
from Back.gestor_señales import GestorSeñales

DURACION_MAXIMA_ENTRE_PICOS = 4
UMBRAL_POSITIVO = 70000
UMBRAL_NEGATIVO = -70000
UMBRAL_VOLUMEN = 10.0
TOLERANCIA_FLUJO = 1.0
FRECUENCIA_CORTE = 5.0

METODOS = (
    "1 - Umbral de volumen",
    "2 - Flujo filtrado + derivada",
)


class VisorMetodos:
    def __init__(self, ventana, gestor):
        self.ventana = ventana
        self.gestor = gestor
        self.señal = None
        self.cache = {}          # nombre_archivo -> dict con series y detecciones
        self.lineas_respiraciones = []

        self.archivo_var = tk.StringVar()
        self.metodo_var = tk.StringVar(value=METODOS[0])
        self.inicio_var = tk.StringVar(value="0.0")
        self.fin_var = tk.StringVar(value="30.0")
        self.estado_var = tk.StringVar(value="Seleccione una señal")

        self._crear_controles()
        self._crear_grafico()
        self._cargar_archivos()

    # ------------------------------------------------------------------ UI ---
    def _crear_controles(self):
        controles = ttk.Frame(self.ventana, padding=10)
        controles.pack(fill=tk.X)

        ttk.Label(controles, text="Señal:").pack(side=tk.LEFT)
        archivos = [archivo.name for archivo in self.gestor.archivos_disponibles()]
        self.selector = ttk.Combobox(
            controles, textvariable=self.archivo_var, values=archivos,
            state="readonly", width=24,
        )
        self.selector.pack(side=tk.LEFT, padx=8)
        self.selector.bind("<<ComboboxSelected>>", self._seleccionar_archivo)

        ttk.Label(controles, text="Método:").pack(side=tk.LEFT, padx=(18, 4))
        self.selector_metodo = ttk.Combobox(
            controles, textvariable=self.metodo_var, values=METODOS,
            state="readonly", width=30,
        )
        self.selector_metodo.pack(side=tk.LEFT)
        self.selector_metodo.bind("<<ComboboxSelected>>", lambda _e: self._cambiar_metodo())

        ttk.Label(controles, text="Desde:").pack(side=tk.LEFT, padx=(18, 4))
        ttk.Entry(controles, textvariable=self.inicio_var, width=8).pack(side=tk.LEFT)
        ttk.Label(controles, text="Hasta:").pack(side=tk.LEFT, padx=(8, 4))
        ttk.Entry(controles, textvariable=self.fin_var, width=8).pack(side=tk.LEFT)
        ttk.Button(controles, text="Aplicar", command=self._aplicar_rango).pack(side=tk.LEFT, padx=6)

        acciones = ttk.Frame(self.ventana, padding=(10, 0, 10, 8))
        acciones.pack(fill=tk.X)
        ttk.Button(acciones, text="|< Principio", command=self._ir_al_principio).pack(side=tk.LEFT)
        ttk.Button(acciones, text="← 10 s", command=lambda: self._mover(-10)).pack(side=tk.LEFT)
        ttk.Button(acciones, text="→ 10 s", command=lambda: self._mover(10)).pack(side=tk.LEFT, padx=5)
        ttk.Button(acciones, text="Final >|", command=self._ir_al_final).pack(side=tk.LEFT)
        ttk.Button(acciones, text="Mostrar todo", command=self._mostrar_todo).pack(side=tk.LEFT)
        ttk.Label(acciones, textvariable=self.estado_var).pack(side=tk.RIGHT)

    def _crear_grafico(self):
        self.figura = Figure(figsize=(10, 8), dpi=100)
        self.ejes = self.figura.subplots(3, 1, sharex=True)
        self.figura.subplots_adjust(left=0.09, right=0.98, top=0.97, bottom=0.08, hspace=0.25)

        colores = ("#1479a8", "#3c8c5a", "#d26a2e")
        etiquetas = ("Flow", "Volumen", "dFlow/dt")
        self.lineas = []
        for eje, color, etiqueta in zip(self.ejes, colores, etiquetas):
            eje.set_ylabel(etiqueta, rotation=0, labelpad=30, fontweight="bold")
            eje.grid(True, alpha=0.25)
            linea, = eje.plot([], [], color=color, linewidth=0.8)
            self.lineas.append(linea)
        self.linea_umbral = self.ejes[1].axhline(
            UMBRAL_VOLUMEN, color="#888", linewidth=0.7, linestyle=":"
        )
        self.ejes[-1].set_xlabel("Tiempo (s)")

        canvas = FigureCanvasTkAgg(self.figura, master=self.ventana)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10)
        self.toolbar = NavigationToolbar2Tk(canvas, self.ventana, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.pack(fill=tk.X, padx=10, pady=(0, 4))
        self.canvas = canvas

    # ------------------------------------------------------------- carga ---
    def _cargar_archivos(self):
        archivos = self.gestor.archivos_disponibles()
        if archivos:
            self.archivo_var.set(archivos[0].name)
            self._cargar_archivo(archivos[0])

    def _seleccionar_archivo(self, _evento=None):
        self._cargar_archivo(ROOT / "datos" / self.archivo_var.get())

    def _cargar_archivo(self, archivo):
        try:
            self.señal = self.gestor.cargar(archivo)
            self._preparar_detecciones(archivo.name)
            self.inicio_var.set("0.00")
            self.fin_var.set(f"{min(30, self.señal.duracion):.2f}")
            self._actualizar_grafico()
        except Exception as error:
            messagebox.showerror("No se pudo cargar la señal", str(error))

    def _preparar_detecciones(self, nombre):
        if nombre in self.cache:
            return
        señal = self.señal
        tiempo_rel = señal.tiempo - señal.inicio

        t_volumen = detectar_respiraciones_por_volumen(
            señal.flujo, señal.tiempo, umbral_volumen=UMBRAL_VOLUMEN,
            tiempo_maximo=DURACION_MAXIMA_ENTRE_PICOS,
        ) - señal.inicio
        t_filtrado, derivada_filtrada = detectar_respiraciones_filtrado(
            señal.flujo, señal.tiempo, fs=señal.fs, frecuencia_corte=FRECUENCIA_CORTE,
            umbral_positivo=UMBRAL_POSITIVO, umbral_negativo=UMBRAL_NEGATIVO,
            tiempo_maximo=DURACION_MAXIMA_ENTRE_PICOS,
        )
        t_filtrado = t_filtrado - señal.inicio

        self.cache[nombre] = {
            "tiempo": tiempo_rel,
            "volumen": señal.volumen,
            "derivada_filtrada": derivada_filtrada,
            "detecciones": {1: t_volumen, 2: t_filtrado},
        }

    # ---------------------------------------------------------- graficado ---
    def _metodo_actual(self):
        return int(self.metodo_var.get()[0])

    def _cambiar_metodo(self):
        self._actualizar_grafico()

    def _aplicar_rango(self):
        try:
            inicio = float(self.inicio_var.get())
            fin = float(self.fin_var.get())
            if self.señal is None or inicio >= fin:
                raise ValueError("El rango no es válido")
            if inicio < 0 or fin > self.señal.duracion:
                raise ValueError("El rango está fuera de la señal")
            self._actualizar_grafico()
        except ValueError as error:
            messagebox.showwarning("Rango inválido", str(error))

    def _actualizar_grafico(self):
        if self.señal is None:
            return
        datos = self.cache[self.archivo_var.get()]
        metodo = self._metodo_actual()
        inicio = float(self.inicio_var.get())
        fin = float(self.fin_var.get())

        tiempo = datos["tiempo"]
        mascara = (tiempo >= inicio) & (tiempo <= fin)
        if not mascara.any():
            return

        series = (self.señal.flujo, datos["volumen"], datos["derivada_filtrada"])
        self.ejes[2].set_ylabel("dFlow/dt filtrada", rotation=0, labelpad=30, fontweight="bold")

        mostrar_deriv = metodo != 1
        self.ejes[2].set_visible(mostrar_deriv)

        self._limpiar_lineas_respiraciones()
        detecciones = datos["detecciones"][metodo]
        visibles = detecciones[(detecciones >= inicio) & (detecciones <= fin)]

        ejes_activos = self.ejes if mostrar_deriv else self.ejes[:2]
        for eje, linea, serie in zip(ejes_activos, self.lineas, series):
            linea.set_data(tiempo[mascara], serie[mascara])
            eje.set_xlim(inicio, fin)
            minimo = float(serie[mascara].min())
            maximo = float(serie[mascara].max())
            margen = max((maximo - minimo) * 0.08, 0.05)
            eje.set_ylim(minimo - margen, maximo + margen)
            for tiempo_respiracion in visibles:
                self.lineas_respiraciones.append(
                    eje.axvline(tiempo_respiracion, color="#d62728",
                                linestyle="--", linewidth=0.8, alpha=0.8)
                )

        self.estado_var.set(
            f"{len(self.señal.data):,} muestras | duración: {self.señal.duracion:.2f} s "
            f"| método {metodo}: {len(detecciones)} respiraciones"
        )
        self.canvas.draw_idle()

    def _limpiar_lineas_respiraciones(self):
        for linea in self.lineas_respiraciones:
            linea.remove()
        self.lineas_respiraciones.clear()

    # -------------------------------------------------------- navegacion ---
    def _mover(self, segundos):
        if self.señal is None:
            return
        inicio = float(self.inicio_var.get()) + segundos
        fin = float(self.fin_var.get()) + segundos
        ancho = fin - inicio
        inicio = max(0, min(inicio, self.señal.duracion - ancho))
        self.inicio_var.set(f"{inicio:.2f}")
        self.fin_var.set(f"{inicio + ancho:.2f}")
        self._actualizar_grafico()

    def _mostrar_todo(self):
        if self.señal is None:
            return
        self.inicio_var.set("0.00")
        self.fin_var.set(f"{self.señal.duracion:.2f}")
        self._actualizar_grafico()

    def _ir_al_principio(self):
        if self.señal is None:
            return
        ancho = float(self.fin_var.get()) - float(self.inicio_var.get())
        self.inicio_var.set("0.00")
        self.fin_var.set(f"{min(ancho, self.señal.duracion):.2f}")
        self._actualizar_grafico()

    def _ir_al_final(self):
        if self.señal is None:
            return
        ancho = min(float(self.fin_var.get()) - float(self.inicio_var.get()),
                    self.señal.duracion)
        self.inicio_var.set(f"{self.señal.duracion - ancho:.2f}")
        self.fin_var.set(f"{self.señal.duracion:.2f}")
        self._actualizar_grafico()


if __name__ == "__main__":
    ventana = tk.Tk()
    ventana.title("Comparador de métodos de detección")
    ventana.geometry("1150x850+100+80")
    ventana.minsize(800, 600)
    VisorMetodos(ventana, GestorSeñales(ROOT / "datos"))
    ventana.mainloop()
