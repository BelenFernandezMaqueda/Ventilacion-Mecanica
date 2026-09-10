import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from Back.gestor_señales import GestorSeñales


class VisorSeñales:
    """Interfaz mínima: el back entrega una Señal y esta clase la dibuja."""

    def __init__(self, ventana, gestor):
        self.ventana = ventana
        self.gestor = gestor
        self.señal = None
        self.archivo_actual = None
        self.respiraciones = []
        self.lineas_respiraciones = []

        self.archivo_var = tk.StringVar()
        self.inicio_var = tk.StringVar(value="0.0")
        self.fin_var = tk.StringVar(value="30.0")
        self.estado_var = tk.StringVar(value="Seleccione una señal")

        self._crear_controles()
        self._crear_grafico()
        self._cargar_archivos()

    def _crear_controles(self):
        controles = ttk.Frame(self.ventana, padding=10)
        controles.pack(fill=tk.X)

        ttk.Label(controles, text="Señal:").pack(side=tk.LEFT)
        archivos = [archivo.name for archivo in self.gestor.archivos_disponibles()]
        self.selector = ttk.Combobox(
            controles,
            textvariable=self.archivo_var,
            values=archivos,
            state="readonly",
            width=28,
        )
        self.selector.pack(side=tk.LEFT, padx=8)
        self.selector.bind("<<ComboboxSelected>>", self._seleccionar_archivo)

        ttk.Label(controles, text="Desde (relativo):").pack(side=tk.LEFT, padx=(18, 4))
        ttk.Entry(controles, textvariable=self.inicio_var, width=8).pack(side=tk.LEFT)
        ttk.Label(controles, text="s").pack(side=tk.LEFT, padx=(3, 8))
        ttk.Label(controles, text="Hasta (relativo):").pack(side=tk.LEFT)
        ttk.Entry(controles, textvariable=self.fin_var, width=8).pack(side=tk.LEFT, padx=(4, 0))
        ttk.Label(controles, text="s").pack(side=tk.LEFT, padx=(3, 8))
        ttk.Button(controles, text="Aplicar", command=self._aplicar_rango).pack(side=tk.LEFT)

        acciones = ttk.Frame(self.ventana, padding=(10, 0, 10, 8))
        acciones.pack(fill=tk.X)
        ttk.Button(acciones, text="|< Principio", command=self._ir_al_principio).pack(side=tk.LEFT)
        ttk.Button(acciones, text="← 10 s", command=lambda: self._mover(-10)).pack(side=tk.LEFT)
        ttk.Button(acciones, text="→ 10 s", command=lambda: self._mover(10)).pack(side=tk.LEFT, padx=5)
        ttk.Button(acciones, text="Final >|", command=self._ir_al_final).pack(side=tk.LEFT)
        ttk.Button(acciones, text="Mostrar todo", command=self._mostrar_todo).pack(side=tk.LEFT)
        ttk.Label(acciones, textvariable=self.estado_var).pack(side=tk.RIGHT)

    def _crear_grafico(self):
        self.figura = Figure(figsize=(10, 9), dpi=100)
        self.ejes = self.figura.subplots(4, 1, sharex=True)
        self.figura.subplots_adjust(left=0.08, right=0.98, top=0.98, bottom=0.08, hspace=0.22)

        self.lineas = {}
        configuracion = [
            ("Flow", "FLOW", "#1479a8"),
            ("Volumen", "VOLUMEN", "#6a51a3"),
            ("Paw", "PAW", "#d26a2e"),
            ("Pes", "PES", "#3c8c5a"),
        ]
        for eje, (columna, titulo, color) in zip(self.ejes, configuracion):
            eje.set_ylabel(titulo, rotation=0, labelpad=28, fontweight="bold")
            eje.grid(True, alpha=0.25)
            self.lineas[columna], = eje.plot([], [], color=color, linewidth=0.8)
        self.ejes[-1].set_xlabel("Tiempo (s)")

        canvas = FigureCanvasTkAgg(self.figura, master=self.ventana)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10)
        self.toolbar = NavigationToolbar2Tk(canvas, self.ventana, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.pack(fill=tk.X, padx=10, pady=(0, 4))
        self.canvas = canvas

    def _cargar_archivos(self):
        archivos = self.gestor.archivos_disponibles()
        if archivos:
            self.archivo_var.set(archivos[0].name)
            self._cargar_archivo(archivos[0])

    def _seleccionar_archivo(self, _evento=None):
        archivo = ROOT / "datos" / self.archivo_var.get()
        self._cargar_archivo(archivo)

    def _cargar_archivo(self, archivo):
        try:
            self.señal = self.gestor.cargar(archivo)
            self.archivo_actual = archivo
            self.respiraciones = self.señal.respiraciones - self.señal.inicio
            self.inicio_var.set("0.00")
            self.fin_var.set(f"{min(30, self.señal.duracion):.2f}")
            self._actualizar_grafico()
            self.estado_var.set(
                f"{len(self.señal.data):,} muestras | "
                f"duración: {self.señal.duracion:.2f} s | "
                f"respiraciones: {len(self.respiraciones)}"
            )
        except Exception as error:
            messagebox.showerror("No se pudo cargar la señal", str(error))

    def _aplicar_rango(self):
        try:
            inicio = float(self.inicio_var.get())
            fin = float(self.fin_var.get())
            if inicio >= fin or self.señal is None:
                raise ValueError("El rango no es válido")
            if inicio < 0 or fin > self.señal.duracion:
                raise ValueError("El rango está fuera de la señal")
            self._actualizar_grafico()
        except ValueError as error:
            messagebox.showwarning("Rango inválido", str(error))

    def _actualizar_grafico(self):
        inicio = float(self.inicio_var.get())
        fin = float(self.fin_var.get())
        segmento = self.señal.segmento(inicio, fin)
        if segmento.empty:
            return

        self._limpiar_lineas_respiraciones()
        for eje, columna in zip(self.ejes, ("Flow", "Volumen", "Paw", "Pes")):
            self.lineas[columna].set_data(segmento["Time"], segmento[columna])
            eje.set_xlim(inicio, fin)
            minimo = float(segmento[columna].min())
            maximo = float(segmento[columna].max())
            margen = max((maximo - minimo) * 0.08, 0.05)
            eje.set_ylim(minimo - margen, maximo + margen)
            for tiempo_respiracion in self.respiraciones:
                self.lineas_respiraciones.append(
                    eje.axvline(
                        tiempo_respiracion,
                        color="#d62728",
                        linestyle="--",
                        linewidth=0.8,
                        alpha=0.8,
                    )
                )
        self.canvas.draw_idle()

    def _limpiar_lineas_respiraciones(self):
        for linea in self.lineas_respiraciones:
            linea.remove()
        self.lineas_respiraciones.clear()

    def _mover(self, segundos):
        if self.señal is None:
            return
        inicio = float(self.inicio_var.get()) + segundos
        fin = float(self.fin_var.get()) + segundos
        ancho = fin - inicio
        inicio = max(0, min(inicio, self.señal.duracion - ancho))
        fin = inicio + ancho
        self.inicio_var.set(f"{inicio:.2f}")
        self.fin_var.set(f"{fin:.2f}")
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
        ancho = float(self.fin_var.get()) - float(self.inicio_var.get())
        ancho = min(ancho, self.señal.duracion)
        inicio = self.señal.duracion - ancho
        self.inicio_var.set(f"{inicio:.2f}")
        self.fin_var.set(f"{self.señal.duracion:.2f}")
        self._actualizar_grafico()


if __name__ == "__main__":
    ventana = tk.Tk()
    ventana.title("Visor de señales")
    ventana.geometry("1100x800+100+100")
    ventana.minsize(800, 600)
    ventana.deiconify()
    ventana.lift()
    ventana.attributes("-topmost", True)
    ventana.after(500, lambda: ventana.attributes("-topmost", False))
    ventana.focus_force()
    VisorSeñales(ventana, GestorSeñales(ROOT / "datos"))
    ventana.mainloop()
