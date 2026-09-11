"""Deteccion de respiraciones con tres metodos distintos.

1. ``detectar_respiraciones``: metodo original, busca un pico positivo y luego
   uno negativo en la derivada del flujo, con umbrales adaptativos.
2. ``detectar_respiraciones_por_volumen``: integra el flujo, pone un umbral al
   volumen y retrocede sobre el flujo hasta el ultimo instante en que fue ~0.
3. ``detectar_respiraciones_filtrado``: aplica un pasabajos al flujo, recalcula
   la derivada, la eleva al cuadrado conservando el signo y reutiliza el metodo
   1 sobre esa derivada.

Nota: ``detectar_respiraciones`` (metodo 1) ya no se recomienda usar de forma
directa. ``detectar_respiraciones_filtrado`` (metodo 3) es su version
optimizada: el pasabajos quita el ruido de alta frecuencia y elevar la derivada
al cuadrado hace que los picos reales resalten mucho mas sobre los falsos, con
lo que la deteccion es mas confiable.
"""

from collections import deque

import numpy as np
from scipy.signal import butter, filtfilt

def detectar_respiraciones(
    derivada,
    tiempo,
    umbral_positivo=70000,
    umbral_negativo=-70000,
    tiempo_maximo=3,
    n_historial=10,
    factor_umbral=0.4,
    muestras_pico_negativo=200,
):
    """Detecta respiraciones con umbrales adaptativos.

    Nota: metodo original, ya no se recomienda usarlo de forma directa. Preferir
    ``detectar_respiraciones_filtrado``, que filtra el flujo y eleva la derivada
    al cuadrado antes de llamar a esta funcion, con lo que los picos reales
    resaltan mas y la deteccion es mas confiable.

    Se marca el inicio cuando la derivada cruza el umbral positivo y se cierra
    la respiracion cuando cruza el negativo, si eso pasa dentro de
    ``tiempo_maximo`` segundos. En lugar de buscar el pico exacto solo mira que
    pase el umbral, lo que lo hace mas robusto a picos falsos/doble picos.

    Los umbrales no son fijos: se arranca con ``umbral_positivo`` /
    ``umbral_negativo`` (repetidos ``n_historial`` veces) y, cada vez que se
    confirma una respiracion valida, se guardan el maximo y el minimo reales de
    la derivada. El maximo se busca en el tramo inicio-cierre; el minimo se busca
    hasta ``muestras_pico_negativo`` muestras despues del cierre, porque el punto
    mas negativo del pico llega despues del cruce del umbral. El umbral vigente en
    cada instante es ``factor_umbral`` por el promedio de los ultimos
    ``n_historial`` picos.
    """

    derivada = np.asarray(derivada, dtype=float)
    tiempo = np.asarray(tiempo, dtype=float)
    picos_positivos = deque([umbral_positivo] * n_historial, maxlen=n_historial)
    picos_negativos = deque([umbral_negativo] * n_historial, maxlen=n_historial)
    adentro_pico_p=False
    respiracion = False
    indice_inicio = 0
    respiraciones = []

    for i in range(len(derivada)):
        umbral_positivo_actual = factor_umbral * sum(picos_positivos) / len(picos_positivos)
        umbral_negativo_actual = (factor_umbral/2) * sum(picos_negativos) / len(picos_negativos)

        if not respiracion and derivada[i] > umbral_positivo_actual:
            respiracion = True
            indice_inicio = i
            adentro_pico_p = True
        elif respiracion and adentro_pico_p and derivada[i] < umbral_positivo_actual:
            adentro_pico_p = False
        elif respiracion and derivada[i] > umbral_positivo_actual and not adentro_pico_p:
            indice_inicio = i
            adentro_pico_p = True
        elif respiracion and derivada[i] < umbral_negativo_actual:
            respiracion = False
            if tiempo[i] - tiempo[indice_inicio] <= tiempo_maximo: #esto es para evitar errores de arrastre!
                respiraciones.append(tiempo[indice_inicio])
                picos_positivos.append(derivada[indice_inicio:i + 1].max())
                # el punto mas negativo del pico llega despues del cruce del
                # umbral, asi que para el historial se busca el minimo un poco
                # mas adelante (``muestras_pico_negativo`` muestras)
                picos_negativos.append(
                    derivada[indice_inicio:i + muestras_pico_negativo].min()
                )

    return np.asarray(respiraciones, dtype=float)


def _minimo_movil(x, ventana):
    """Minimo movil centrado, O(n), usando una cola monotona."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    if ventana <= 1 or n == 0:
        return x.copy()
    ventana = min(ventana, n)
    mitad = ventana // 2
    resultado = np.empty(n)
    cola = deque()
    for derecha in range(n):
        while cola and x[cola[-1]] >= x[derecha]:
            cola.pop()
        cola.append(derecha)
        if cola[0] <= derecha - ventana:
            cola.popleft()
        centro = derecha - mitad
        if centro >= 0:
            resultado[centro] = x[cola[0]]
    # Los ultimos ``mitad`` centros nunca completan la ventana a derecha:
    # se calculan directamente sobre la ventana recortada.
    for centro in range(max(0, n - mitad), n):
        resultado[centro] = x[max(0, centro - mitad):n].min()
    return resultado


def calcular_volumen(
    flujo,
    tiempo,
    corregir_deriva=True,
    ventana_baseline_s=8.0,
):
    """Integra el flujo para obtener el volumen.

    El flujo suele tener un offset y una deriva lenta que hacen que la integral
    se aleje de cero. Por eso se le resta la media y, si ``corregir_deriva`` es
    ``True``, se resta ademas una linea de base (minimo movil) para que el
    volumen vuelva a ~0 entre respiraciones.
    """
    flujo = np.asarray(flujo, dtype=float)
    tiempo = np.asarray(tiempo, dtype=float)
    if len(flujo) != len(tiempo):
        raise ValueError("flujo y tiempo deben tener la misma longitud")
    if len(flujo) < 2:
        return np.zeros_like(flujo)

    dt = np.diff(tiempo)
    flujo_sin_offset = flujo - flujo.mean()
    incrementos = (flujo_sin_offset[1:] + flujo_sin_offset[:-1]) / 2 * dt
    volumen = np.concatenate([[0.0], np.cumsum(incrementos)])

    if corregir_deriva:
        fs = 1.0 / np.median(dt)
        ventana = max(3, int(round(ventana_baseline_s * fs)))
        volumen = volumen - _minimo_movil(volumen, ventana)

    return volumen


def detectar_respiraciones_por_volumen(
    flujo,
    tiempo,
    umbral_volumen=10.0,
    ventana_baseline_s=8.0,
    tiempo_maximo=0.5
):
    """Detecta respiraciones a partir del volumen integrado.

    Recorre el volumen; cuando supera ``umbral_volumen`` marca una respiracion.
    El comienzo se busca **sobre el flujo**: se retrocede desde ese punto hasta
    el ultimo instante en que el flujo todavia era ~0
    (``<= tolerancia_flujo``), es decir el arranque de la inspiracion. Luego
    avanza hasta que el volumen vuelve a ~0 antes de buscar la siguiente.
    """
    flujo = np.asarray(flujo, dtype=float)
    tiempo = np.asarray(tiempo, dtype=float)
    volumen = calcular_volumen(
        flujo, tiempo, ventana_baseline_s=ventana_baseline_s
    )

    sobre_umbral = False
    respiraciones = []

    for i in range(len(volumen)):
        if not sobre_umbral and volumen[i] > umbral_volumen:
            sobre_umbral = True
            tiempo_inicio = tiempo[i]
        elif sobre_umbral and volumen[i] < umbral_volumen:
            sobre_umbral = False
            tiempo_fin = tiempo[i]
            if tiempo_fin - tiempo_inicio <= tiempo_maximo: #esto es para evitar errores de arrastre!
                respiraciones.append(tiempo_inicio)

    return np.asarray(respiraciones, dtype=float)


def filtrar_pasabajos(x, fs, frecuencia_corte=3.0, orden=4):
    """Pasabajos Butterworth de fase cero, via ``scipy.signal.filtfilt``.
    """
    x = np.asarray(x, dtype=float)
    n = len(x)
    if n < 4 or frecuencia_corte <= 0 or frecuencia_corte >= fs / 2:
        return x.copy()

    b, a = butter(orden, frecuencia_corte, btype="low", fs=fs)
    padlen = 3 * max(len(a), len(b))
    if n <= padlen:
        return x.copy()

    return filtfilt(b, a, x)


def detectar_respiraciones_filtrado(
    flujo,
    tiempo,
    fs=256,
    frecuencia_corte=3.0,
    umbral_positivo=70000,
    umbral_negativo=-70000,
    tiempo_maximo=2,
):
    """Filtra el flujo con un pasabajos, recalcula la derivada, la eleva al
    cuadrado conservando el signo y aplica ``detectar_respiraciones`` sobre esa
    derivada.

    Es el metodo recomendado: el pasabajos saca el ruido de alta frecuencia y
    el cuadrado exagera los picos reales frente a los falsos.

    Devuelve ``(tiempos, derivada_filtrada)``.
    """
    flujo = np.asarray(flujo, dtype=float)
    tiempo = np.asarray(tiempo, dtype=float)

    flujo_filtrado = filtrar_pasabajos(flujo, fs, frecuencia_corte=frecuencia_corte)
    derivada_filtrada = np.gradient(flujo_filtrado, tiempo)
    derivada_filtrada = np.sign(derivada_filtrada) * derivada_filtrada**2 #esto lo que hace es mantener el signo pero  en valor absoluto eleva al cuadrado, es decir que los que son positivos se vuelven mas positivos y los negativos mas negativos, esto hace que los picos sean mas pronunciados y por lo tanto mas faciles de detectar

    tiempos = detectar_respiraciones(
        derivada_filtrada,
        tiempo,
        umbral_positivo=umbral_positivo,
        umbral_negativo=umbral_negativo,
        tiempo_maximo=tiempo_maximo,
    )
    return tiempos, derivada_filtrada
