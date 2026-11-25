"""Carga los resultados de Kaggle en RDS for PostgreSQL (base "airbnb") y crea las vistas.

Tablas: anuncios, predicciones, metricas_modelos. Vistas: db/vistas.sql.
Se puede volver a ejecutar: reemplaza las tablas y recrea las vistas.

Uso (en la ECS):
    docker compose run --rm app python scripts/cargar_postgres.py
"""
import os
import pathlib
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine, text

DATA = pathlib.Path(os.getenv("DATA_DIR", "/data"))
VISTAS = pathlib.Path(__file__).resolve().parent.parent / "db" / "vistas.sql"


def motor(base=None):
    url = (f"postgresql+psycopg2://{os.environ['PG_USER']}:{quote_plus(os.environ['PG_PASSWORD'])}"
           f"@{os.environ['PG_HOST']}:{os.getenv('PG_PORT', '5432')}/{base or os.getenv('PG_DB', 'airbnb')}")
    return create_engine(url, connect_args={"connect_timeout": 10})


def minusculas(df):
    df.columns = [c.lower() for c in df.columns]
    return df


def main():
    anuncios = minusculas(pd.read_parquet(DATA / "anuncios.parquet"))
    predicciones = minusculas(pd.read_parquet(DATA / "predicciones.parquet"))
    metricas = pd.read_csv(DATA / "metricas_modelos.csv").rename(
        columns={"mejora_rmse_vs_base_%": "mejora_vs_base_pct"})

    eng = motor()
    with eng.begin() as con:   # las vistas dependen de las tablas: se borran antes de reemplazarlas
        con.execute(text("DROP VIEW IF EXISTS v_localidad, v_legalidad, v_quintil, v_estrato, v_modelos CASCADE"))

    for nombre, df in [("anuncios", anuncios), ("predicciones", predicciones), ("metricas_modelos", metricas)]:
        df.to_sql(nombre, eng, if_exists="replace", index=False, chunksize=2000, method="multi")
        print(f"Tabla {nombre}: {len(df):,} filas")

    sql = "\n".join(l for l in VISTAS.read_text(encoding="utf-8").splitlines()
                    if not l.lstrip().startswith("--"))          # quita comentarios antes de separar
    sentencias = [s.strip() for s in sql.split(";") if s.strip()]
    with eng.begin() as con:
        for s in sentencias:
            con.execute(text(s))
        for v in ["v_localidad", "v_legalidad", "v_quintil", "v_estrato", "v_modelos"]:
            n = con.execute(text(f"SELECT COUNT(*) FROM {v}")).scalar()
            print(f"Vista {v}: {n} filas")
    print("Carga terminada.")


if __name__ == "__main__":
    main()
