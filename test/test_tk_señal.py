import sys
from pathlib import Path

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from Back.convertir_a_df import convertir_a_df


# ============================================================
# DATOS
# ============================================================

archivo = ROOT / "datos" / "Mini TP Signals A.txt"

datos = convertir_a_df(archivo)

segmento = datos[
    (datos["Time"] >= 0) &
    (datos["Time"] <= 30)
]


# ============================================================
# VENTANA
# ============================================================

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

ventana = ctk.CTk()

ventana.title("Señal A")
ventana.geometry("1000x600+100+100")


# ============================================================
# HEADER
# ============================================================

header = ctk.CTkFrame(ventana, corner_radius=0)
header.pack(fill="x", padx=15, pady=(15, 5))

titulo = ctk.CTkLabel(
    header,
    text="Visualización de señal",
    font=ctk.CTkFont(size=20, weight="bold")
)
titulo.pack(anchor="w", padx=15, pady=(10, 0))

etiqueta = ctk.CTkLabel(
    header,
    text=f"{archivo.name}  |  {len(segmento)} muestras  |  0–30 segundos",
    font=ctk.CTkFont(size=13)
)
etiqueta.pack(anchor="w", padx=15, pady=(2, 10))


# ============================================================
# CONTENEDOR DEL GRÁFICO
# ============================================================

frame_grafico = ctk.CTkFrame(
    ventana,
    corner_radius=10
)

frame_grafico.pack(
    fill="both",
    expand=True,
    padx=15,
    pady=10
)


# ============================================================
# MATPLOTLIB
# ============================================================

figura = Figure(
    figsize=(10, 5),
    dpi=100
)

eje = figura.add_subplot(111)

eje.plot(
    segmento["Time"],
    segmento["Flow"],
    color="#1479a8",
    linewidth=0.8
)

eje.set_title("FLOW")
eje.set_xlabel("Tiempo (s)")
eje.set_ylabel("Flujo")
eje.grid(True, alpha=0.25)
eje.set_xlim(0, 30)

figura.tight_layout()


# ============================================================
# CANVAS
# ============================================================

canvas = FigureCanvasTkAgg(
    figura,
    master=frame_grafico
)

canvas.draw()

canvas.get_tk_widget().pack(
    fill="both",
    expand=True,
    padx=10,
    pady=10
)


# ============================================================
# START
# ============================================================

ventana.mainloop()