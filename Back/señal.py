"""Modelo de una señal respiratoria cargada en memoria."""

import numpy as np

from Back.detectar_respiracion import calcular_volumen, detectar_respiraciones_filtrado


class Señal:
    def __init__(self, df, fs=256):
        self.data = df
        self.fs = fs
        self.tiempo = df["Time"].to_numpy()
        self.flujo = df["Flow"].to_numpy()
        self.paw = df["Paw"].to_numpy()
        self.pes = df["Pes"].to_numpy()
        self.Fderiv = np.gradient(self.flujo, self.tiempo)
        self.volumen = calcular_volumen(self.flujo, self.tiempo)

        # tiempos (absolutos) donde arranca cada respiracion detectada
        self.respiraciones, _ = detectar_respiraciones_filtrado(
            self.flujo, self.tiempo, fs=self.fs
        )

    @property
    def inicio(self):
        return float(self.tiempo.min())

    @property
    def fin(self):
        return float(self.tiempo.max())

    @property
    def duracion(self):
        return self.fin - self.inicio

    def segmento(self, inicio, fin):
        """Devuelve un segmento usando tiempo relativo al comienzo de la señal."""
        inicio_absoluto = self.inicio + inicio
        fin_absoluto = self.inicio + fin
        mascara = (
            (self.data["Time"] >= inicio_absoluto)
            & (self.data["Time"] <= fin_absoluto)
        )
        segmento = self.data[mascara].copy()
        segmento["Time"] = segmento["Time"] - self.inicio
        segmento["Fderiv"] = self.Fderiv[mascara.to_numpy()]
        segmento["Volumen"] = self.volumen[mascara.to_numpy()]
        return segmento