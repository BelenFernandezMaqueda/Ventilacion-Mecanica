import pandas as pd


def convertir_a_df(filepath):
    """
    Carga un archivo de señales en formato .txt y lo devuelve como un DataFrame de pandas.

    Returns
    -------
    pd.DataFrame
        DataFrame con las señales.
    """

    df = pd.read_csv(
        filepath,
        sep="\t",
        skiprows=5
    )

    return df
