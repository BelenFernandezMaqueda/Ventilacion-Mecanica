from pathlib import Path
import sys

raiz_proyecto = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(raiz_proyecto))
from Back.convertir_a_df import convertir_a_df


archivo = raiz_proyecto / "datos" / "Mini TP Signals A.txt"
señal = convertir_a_df(archivo)

print("Nombres de las columnas:")
print(señal.columns)

print("\nPrimeras filas:")
print(señal.head())

#se genera una columna extra al final por una tabulacion demas pero no afecta el funcionamiento