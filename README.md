# Detección de respiraciones en señales de ventilación mecánica

Dado un registro de señales de un ventilador (Flow, Volume, Paw, Pes, …), el
objetivo es poder mostrar dichas señales de forma cómoda y detectar automáticamente el instante de inicio de cada
respiración.

---

## 1. Cómo correr

### Requisitos

- Python 3.11+
- `numpy`, `pandas`, `matplotlib` (y `tkinter`, que viene con Python).

```bash
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Visor principal

```bash
python Front/main.py
```

Abre una ventana con 4 paneles (**FLOW, VOLUMEN, PAW, PES**). Tiene selector de
archivo y navegación temporal (Desde / Hasta, botones `← 10 s` / `→ 10 s`,
`Mostrar todo`). Las respiraciones detectadas se marcan con **líneas verticales
rojas punteadas**.

### Comparador de métodos (para testear)

```bash
python test/test_tres_metodos.py
```

Mismo visor pero con un selector de método (umbral de volumen / flujo filtrado)
y paneles extra de volumen y derivada. Sirve para comparar visualmente cómo
detecta cada método sobre cada señal.

El método por umbral de volumen tiene bastantes más errores, pero no porque el
concepto no funcione: no le dediqué tiempo a pulirlo como al otro. Para entender
casos raros del método elegido, esta vista + `debug_deteccion.py`.

### Script de debug de la detección

```bash
python test/debug_deteccion.py
```

Se elige señal y ventana de tiempo en las constantes de arriba del archivo
(`ARCHIVO`, `T_INICIO`, `T_FIN`). Imprime cómo evolucionan las variables
internas del detector (umbrales adaptativos, estado de la máquina de estados,
eventos) **solo cuando algo cambia**, y genera `test/debug_deteccion.png` con la
derivada, *shading* de color por estado y líneas verticales por evento. Fue la
herramienta principal para diagnosticar los problemas del método.

---

## 2. Estructura del proyecto

```
Back/
  convertir_a_df.py        lee el .txt del ventilador a un DataFrame
  señal.py                 clase Señal: envuelve el DataFrame y calcula todo lo derivado
  gestor_señales.py        lista los .txt de datos/ y arma objetos Señal
  detectar_respiracion.py  los 3 métodos de detección + helpers
Front/
  main.py                  visor (tkinter + matplotlib)
datos/                     los 4 registros: Mini TP Signals A–D
test/                      scripts de exploración y visores
```

**`Señal`** expone `tiempo`, `flujo`, `paw`, `pes`, `Fderiv` (derivada del
flujo), `volumen` (flujo integrado) y `respiraciones` (tiempos detectados), y
`segmento(inicio, fin)` recorta con tiempo relativo al inicio. Todo el cálculo
vive en el back: el front solo consulta el objeto.

---

## 3. El método de detección

### Idea general

Una respiración arranca con la **inspiración** (el flujo sube rápido → la
derivada del flujo es positiva y grande) y termina con la **espiración** (el
flujo baja rápido → derivada negativa y grande). Entonces se busca, sobre la
derivada del flujo, un **pico positivo seguido de un pico negativo**.

### Los tres métodos que se probaron

| # | Función | Idea | Resultado |
|---|---|---|---|
| 1 | `detectar_respiraciones` | Umbral sobre la derivada **cruda** del flujo: abre al cruzar un umbral positivo, cierra al cruzar uno negativo. No busca el pico exacto, solo que se pase el umbral (robusto a doble pico). | Base del método 3, pero sola no alcanza: mucho ruido, umbral no generalizable. |
| 2 | `detectar_respiraciones_por_volumen` | Integra el flujo para obtener volumen (con corrección de deriva) y marca respiración cuando supera un umbral. | Descartado como principal: el umbral fijo sobre el volumen integrado es frágil. Queda en el comparador. |
| **3** | **`detectar_respiraciones_filtrado`** ← **elegido** | Pasabajos al flujo → derivada → eleva la derivada al cuadrado (con signo) → aplica el método 1 sobre eso. | Ver §4. |

### Cómo funciona el método elegido (método 3)

1. **Pasabajos de fase cero** al flujo (magnitud tipo Butterworth vía FFT, corte
   5 Hz). Quita el ruido de alta frecuencia **sin desfasar** la señal (no corre
   los tiempos de las respiraciones).
2. **Derivada** del flujo filtrado.
3. **Cuadrado conservando el signo**: `sign(d) · d²`. Los picos grandes
   (respiraciones reales) crecen muchísimo más que los chicos (ruido residual),
   así que mejora la relación señal/ruido *antes* de umbralar.
4. **Método 1** sobre esa derivada: la máquina de estados
   - *fuera de respiración* + derivada > U⁺ → **abre**, guarda el índice de inicio
   - *dentro del pico +* + derivada < U⁺ → salió del pico positivo
   - *fuera del pico +* + derivada > U⁺ de nuevo → **segundo pico positivo** en la misma respiración (doble pico): mueve el inicio al último, que es el más cercano al pico negativo
   - *en respiración* + derivada < U⁻ → **cierra**; si duró ≤ `tiempo_maximo`, se
     registra

**Umbrales adaptativos.** `U⁺` y `U⁻` no son fijos: se lleva un historial de los
últimos `n_historial = 10` picos positivos y negativos **reales** (sembrado al
principio con el umbral inicial), y el umbral vigente es
`factor_umbral = 0.4 ×` el promedio de ese historial. El detector se autoajusta
a la amplitud de cada señal y de cada tramo.

**Pico negativo real.** Al cerrar, el mínimo que entra al historial se busca
hasta 200 muestras (~0.8 s) **después** del cruce del umbral, porque el punto
más profundo del pico negativo aparece bastante después de ese cruce.

## 4. Secuencia de cómo se fue optimizando

1. **Método 1 sobre la derivada cruda.** Andaba, pero detectaba ruido como
   respiraciones y el umbral no generalizaba entre señales.
2. **Método 2 (volumen).** Se probó integrar el flujo con corrección de deriva.
   El umbral fijo sobre el volumen integrado resultó frágil y descartaba
   respiraciones. Se descartó como método principal; se podría retomar tras un
   par de optimizaciones, no se hizo porque me emocionaba más el otro.
3. **Pasabajos al flujo (→ método 3).** Filtrar antes de derivar eliminó casi
   todos los falsos positivos de alta frecuencia.
4. **Cuadrado con signo de la derivada.** Exagera los picos reales frente a los
   residuales → el resultado se vuelve mucho menos sensible a la elección exacta
   del umbral. Esta idea surgio a partir del aloritmo de Pan-Tompkins que tambien trabaja 'exagerando' los picos. La gran diferencia es que aca se guarda el signo.

5. **Umbrales adaptativos.** En vez de un valor fijo, el promedio de los últimos
   N picos reales. Con esto el mismo código anda en las 4 señales sin tocar
   parámetros.
6. **Factor `0.4`.** Con el umbral = promedio pleno, el detector *se ahogaba
   solo*: a medida que el historial se llenaba de picos reales, el umbral subía
   hasta la altura de los picos y dejaba de detectar. Bajarlo a `0.4 × promedio`
   lo estabilizó.
7. **Doble pico positivo.** En la señal D hay respiraciones con dos subidas
   antes de la espiración. Se agregó el sub-estado "dentro / fuera del pico +"
   para quedarse con la subida más cercana al pico negativo.
8. **Colapso del umbral negativo** (bug encontrado con `debug_deteccion.py`). El
   mínimo que se guardaba en el historial se tomaba **justo en el cruce** del
   umbral, nunca en el pico real → entraban valores cercanos a 0 → `U⁻`
   colapsaba a ~0 → cualquier bajadita mínima cerraba la respiración y **una
   sola respiración real se partía en dos**. Se corrigió buscando el mínimo
   hasta 200 muestras después del cruce.
9. **Pico negativo demasiado chico (Señal A, ~615 s).** Una única respiración
   que no se registraba. Se corrigió haciendo que el factor del umbral negativo
   sea la mitad del positivo. Puede ser *overfitting* a ese caso, pero no rompió
   nada más.


---

## 5. Qué se podría mejorar

### Casos concretos observados

- **Arranque de la señal (Señal A).** Cuando empieza la señal real (~505 s) hay
  un par de detecciones falsas antes de que el patrón se estabilice. Caminos:
  más filtrado (bajar la frecuencia de corte del pasabajos, o un filtro de
  mediana previo), o exigir un **volumen mínimo** por respiración (combinar el
  método 3 con el 2 como validación).

- **Posible falso positivo (Señal B, ~425 s).** Hay una respiración detectada en
  medio de un test de voluntad de respiración; no tengo certeza de si
  corresponde. Desde la derivada es indistinguible de una normal, pero un
  chequeo extra sobre el volumen podría resolverlo.

- **Respiraciones dobles (Señal D, ~110–120 s).** Hay respiraciones raras donde
  no está claro si deberían contarse como una o como dos. Decidí no registrarlas
  como dobles.

### Mejoras estructurales

- **Sin ground-truth.** Todo el ajuste fue visual sobre las 4 señales. Con
  respiraciones marcadas a mano se podría medir precisión / recall y ajustar los
  parámetros con un criterio objetivo en vez de a ojo.

- **Volumen.** Se sigue observando bastante deriva (no siempre llega a 0). Se
  podría optimizar el filtro de deriva para que sea más estable.

- **Performance.** El detector es un `for` en Python sobre todas las muestras
  (~430 k en la señal D). Corre rápido, pero para tiempo real o señales muy
  largas habría que vectorizarlo.
