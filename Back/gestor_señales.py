from pathlib import Path

from Back.convertir_a_df import convertir_a_df
from Back.señal import Señal


class GestorSeñales:
    """Carga señales disponibles y devuelve objetos Señal."""

    def __init__(self, carpeta_datos):
        self.carpeta_datos = Path(carpeta_datos)

    def archivos_disponibles(self):
        return sorted(self.carpeta_datos.glob("*.txt"))

    def cargar(self, archivo):
        ruta = Path(archivo)
        datos = convertir_a_df(ruta)
        return Señal(datos)
