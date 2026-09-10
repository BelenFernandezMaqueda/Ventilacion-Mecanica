from pathlib import Path
import sys


raiz_proyecto = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(raiz_proyecto))

from Back.convertir_a_df import convertir_a_df
from Back.señal import Señal


archivo = raiz_proyecto / "datos" / "Mini TP Signals A.txt"
datos = convertir_a_df(archivo)

objeto_señal = Señal(datos)

print("Objeto creado:", objeto_señal)
print("Frecuencia de muestreo:", objeto_señal.fs)
print("Cantidad de muestras:", len(objeto_señal.tiempo))
