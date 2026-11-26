"""App de presentación: precio de Airbnb en Bogotá frente al valor de la propiedad y la legalidad (RNT).

Lee los datos de RDS for PostgreSQL. Si la base no responde (por ejemplo, al probar en tu computador),
usa los archivos de DATA_DIR. El modelo y sus metadatos siempre se leen de DATA_DIR.
"""
import json
import os
import pathlib
from urllib.parse import quote_plus

import altair as alt
import joblib
import numpy as np
import pandas as pd
import streamlit as st

DATA = pathlib.Path(os.getenv("DATA_DIR", "/data"))
AQUI = pathlib.Path(__file__).resolve().parent
MLFLOW_URL = os.getenv("MLFLOW_URL", "")
LEGAL = ["RNT activo Bogotá", "código no encontrado", "código de otro municipio", "sin código"]
COLOR_LEGAL = {"RNT activo Bogotá": "#2e7d32", "código no encontrado": "#c62828",
               "código de otro municipio": "#ef6c00", "sin código": "#6a1b9a"}
NOMBRES = {"banos": "número de baños", "bedrooms": "habitaciones", "accommodates": "huéspedes",
           "log1p_minimum_nights": "noches mínimas", "dist_zona_t_km": "distancia a la Zona T",
           "dist_centro_int_km": "distancia al Centro Internacional", "log_valor_suelo_m2": "valor del suelo",
           "log_avaluo": "avalúo catastral", "neighbourhood_cleansed": "localidad",
           "property_type": "tipo de alojamiento", "grupo_legal": "situación frente al RNT"}
AMENIDADES = {"am_wifi": "Wifi", "am_cocina": "Cocina", "am_lavadora": "Lavadora",
              "am_espacio_trabajo": "Espacio de trabajo", "am_ascensor": "Ascensor",
              "am_gimnasio": "Gimnasio", "am_piscina": "Piscina", "am_parqueadero": "Parqueadero"}

st.set_page_config(page_title="Airbnb Bogotá: precio, valor y legalidad", page_icon="🏙️", layout="wide")


def cop(x):
    return "COP " + f"{x:,.0f}".replace(",", ".")


def num(x, d=2):
    return f"{x:.{d}f}".replace(".", ",")


# ---------------------------------------------------------------- datos
@st.cache_data(ttl=3600, show_spinner="Cargando datos…")
def cargar_datos():
    try:
        from sqlalchemy import create_engine
        url = (f"postgresql+psycopg2://{os.environ['PG_USER']}:{quote_plus(os.environ['PG_PASSWORD'])}"
               f"@{os.environ['PG_HOST']}:{os.getenv('PG_PORT', '5432')}/{os.getenv('PG_DB', 'airbnb')}")
        eng = create_engine(url, connect_args={"connect_timeout": 5})
        anuncios = pd.read_sql("SELECT * FROM anuncios", eng)
        pred = pd.read_sql("SELECT * FROM predicciones", eng)
        metricas = pd.read_sql("SELECT * FROM v_modelos", eng)
        fuente = "PostgreSQL"
    except Exception:
        anuncios = pd.read_parquet(DATA / "anuncios.parquet")
        pred = pd.read_parquet(DATA / "predicciones.parquet")
        metricas = pd.read_csv(DATA / "metricas_modelos.csv").rename(
            columns={"mejora_rmse_vs_base_%": "mejora_vs_base_pct"}).sort_values("rmse_log")
        fuente = "archivos locales"
    for df in (anuncios, pred):
        df.columns = [c.lower() for c in df.columns]
    return anuncios, pred, metricas, fuente


@st.cache_resource(show_spinner="Cargando el modelo…")
def cargar_modelo():
    modelo = joblib.load(DATA / "modelo_final.joblib")
    meta = json.loads((DATA / "meta_simulador.json").read_text(encoding="utf-8"))
    return modelo, meta


def cargar_resumen():
    ruta = AQUI / "resumen_modelos.json"
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}


anuncios, pred, metricas, fuente = cargar_datos()
modelo, meta = cargar_modelo()
resumen = cargar_resumen()
activos = anuncios[anuncios["activo"] == 1]

st.title("Airbnb en Bogotá: ¿el precio refleja el valor de la propiedad?")
st.caption(f"Inside Airbnb (sep. 2026) · Catastro Bogotá 2026 · RNT · Aptología · Estratificación SDP — "
           f"{len(anuncios):,} anuncios · datos desde {fuente}".replace(",", "."))

t_res, t_mapa, t_hip, t_mod, t_sim = st.tabs(["Resumen", "Mapa", "Hipótesis", "Modelos", "Simulador"])

# ---------------------------------------------------------------- resumen
with t_res:
    st.markdown("**Pregunta:** ¿cómo se relaciona el precio por noche de los anuncios de Airbnb en Bogotá con "
                "el valor de la propiedad de su manzana, y cambia esa relación según la situación del anuncio "
                "frente al Registro Nacional de Turismo (RNT)?")
    mejor = metricas.iloc[0]
    c = st.columns(4)
    c[0].metric("Anuncios analizados", f"{len(anuncios):,}".replace(",", "."))
    c[1].metric("Precio mediano por noche", cop(anuncios["precio"].median()))
    c[2].metric("Con RNT activo en Bogotá", f"{100 * (anuncios['grupo_legal'] == LEGAL[0]).mean():.1f} %".replace(".", ","))
    c[3].metric(f"Mejor modelo: {mejor['modelo']}", f"R² = {num(mejor['r2_log'])}",
                f"{num(mejor['mejora_vs_base_pct'], 1)} % menos error que la línea base")

    h1, h2 = resumen.get("h1", {}), resumen.get("h2", {})
    if h1:
        st.subheader("Hallazgos")
        st.markdown(
            f"- **H1 – Valor del suelo:** con controles de ubicación y del anuncio, la elasticidad es "
            f"{num(h1['elasticidad'], 3)} (IC 95 %: {num(h1['ic95'][0], 3)} a {num(h1['ic95'][1], 3)}). "
            "El valor del suelo explica poco una vez se conoce la ubicación del anuncio.\n"
            f"- **H2 – Legalidad:** prueba F de pendientes iguales p = {num(h2['p'], 3)}. Solo el grupo "
            "«código no encontrado» se aparta, y esos anuncios son algo más baratos.\n"
            "- **H3 – Brecha de renta:** el ingreso de Airbnb frente al arriendo tradicional es mayor en las "
            "zonas de menor valor del suelo y de menor estrato (ver pestaña Hipótesis).")

# ---------------------------------------------------------------- mapa
with t_mapa:
    col1, col2 = st.columns([1, 3])
    with col1:
        locs = sorted(anuncios["neighbourhood_cleansed"].unique())
        sel = st.multiselect("Localidades", locs, default=locs)
        color_por = st.radio("Colorear por", ["Grupo frente al RNT", "Precio por noche"])
        if color_por == "Grupo frente al RNT":
            for g, colr in COLOR_LEGAL.items():
                st.markdown(f"<span style='color:{colr}'>●</span> {g}", unsafe_allow_html=True)
        else:
            st.markdown("Quintiles de precio: <span style='color:#fde725'>●</span> más barato → "
                        "<span style='color:#440154'>●</span> más caro", unsafe_allow_html=True)
    d = anuncios[anuncios["neighbourhood_cleansed"].isin(sel)].copy()
    if color_por == "Grupo frente al RNT":
        d["color"] = d["grupo_legal"].map(COLOR_LEGAL)
    else:
        paleta = np.array(["#fde725", "#5ec962", "#21918c", "#3b528b", "#440154"])
        d["color"] = paleta[pd.qcut(d["precio"].rank(method="first"), 5, labels=False).to_numpy()]
    with col2:
        st.map(d, latitude="latitude", longitude="longitude", color="color", size=25, zoom=11)
        st.caption("Inside Airbnb desplaza la ubicación publicada hasta unos 150 m para proteger la privacidad.")

# ---------------------------------------------------------------- hipótesis
with t_hip:
    st.subheader("H1. Precio frente al valor del suelo")
    muestra = anuncios.sample(min(3000, len(anuncios)), random_state=42)
    base = alt.Chart(muestra).encode(
        x=alt.X("log_valor_suelo_m2:Q", title="log(valor del suelo por m²)", scale=alt.Scale(zero=False)),
        y=alt.Y("log_precio:Q", title="log(precio por noche)", scale=alt.Scale(zero=False)))
    st.altair_chart(base.mark_circle(size=12, opacity=0.25)
                    + base.transform_regression("log_valor_suelo_m2", "log_precio").mark_line(color="red"),
                    width="stretch")
    pend = np.polyfit(anuncios["log_valor_suelo_m2"], anuncios["log_precio"], 1)[0]
    texto = f"Sin controles, la pendiente es {num(pend)}: un 10 % más de valor del suelo va con un precio {num(100 * (1.1 ** pend - 1), 1)} % mayor."
    if resumen.get("h1"):
        texto += (f" Al controlar por ubicación (localidad, distancia a la Zona T) y características del anuncio, "
                  f"baja a {num(resumen['h1']['elasticidad'], 3)} y deja de ser significativa al 5 %.")
    st.write(texto)

    st.subheader("H2. ¿Cambia la relación según la legalidad?")
    if resumen.get("h2"):
        h2 = resumen["h2"]
        st.dataframe(pd.DataFrame({"Grupo frente al RNT": list(h2["pendientes"]),
                                   "Elasticidad": [num(v, 3) for v in h2["pendientes"].values()]}),
                     hide_index=True)
        st.write(f"Prueba F de pendientes iguales: F = {num(h2['F'])}, p = {num(h2['p'], 3)}.")
    leg = (anuncios.groupby("grupo_legal")["precio"].agg(anuncios="size", precio_mediano="median")
           .reindex(LEGAL).reset_index())
    leg.columns = ["Grupo frente al RNT", "Anuncios", "Precio mediano por noche"]
    st.dataframe(leg.style.format({"Anuncios": lambda n: f"{n:,}".replace(",", "."),
                                   "Precio mediano por noche": cop}), hide_index=True)

    st.subheader("H3. Brecha de renta (ingreso Airbnb ÷ arriendo tradicional)")
    c1, c2 = st.columns(2)
    q = activos.groupby("quintil_suelo")["brecha_renta"].median().reset_index()
    c1.altair_chart(alt.Chart(q).mark_bar(color="#3b6ea5").encode(
        x=alt.X("quintil_suelo:N", title="Quintil del valor del suelo"),
        y=alt.Y("brecha_renta:Q", title="Brecha mediana")), width="stretch")
    e = activos.dropna(subset=["estrato"]).groupby("estrato")["brecha_renta"].agg(["median", "size"]).reset_index()
    e = e[e["size"] >= 30]
    c2.altair_chart(alt.Chart(e).mark_bar(color="#ef6c00").encode(
        x=alt.X("estrato:O", title="Estrato"), y=alt.Y("median:Q", title="Brecha mediana")),
        width="stretch")
    st.caption("Solo anuncios activos. Brecha < 1: Airbnb rinde menos que el arriendo tradicional del mismo estrato. "
               "Estratos con menos de 30 anuncios se omiten.")

# ---------------------------------------------------------------- modelos
with t_mod:
    st.subheader("Comparación de modelos en la prueba")
    tabla = metricas.rename(columns={"modelo": "Modelo", "rmse_log": "RMSE (log)", "mae_log": "MAE (log)",
                                     "r2_log": "R² (log)", "mae_cop": "MAE (COP)",
                                     "mejora_vs_base_pct": "Mejora vs. base (%)"})
    st.dataframe(tabla.style.format({"RMSE (log)": lambda v: num(v, 3), "MAE (log)": lambda v: num(v, 3), "R² (log)": lambda v: num(v, 3),
                                     "MAE (COP)": cop, "Mejora vs. base (%)": lambda v: num(v, 1)}), hide_index=True)
    c1, c2 = st.columns(2)
    c1.altair_chart(alt.Chart(metricas).mark_bar(color="#3b6ea5").encode(
        x=alt.X("rmse_log:Q", title="RMSE (log) – menor es mejor"), y=alt.Y("modelo:N", sort="x", title=None)),
        width="stretch")
    lim = [float(pred[["log_precio_real", "log_precio_pred"]].min().min()),
           float(pred[["log_precio_real", "log_precio_pred"]].max().max())]
    puntos = alt.Chart(pred).mark_circle(size=10, opacity=0.3).encode(
        x=alt.X("log_precio_real:Q", title="log(precio) real", scale=alt.Scale(domain=lim)),
        y=alt.Y("log_precio_pred:Q", title="log(precio) predicho", scale=alt.Scale(domain=lim)))
    diag = alt.Chart(pd.DataFrame({"x": lim, "y": lim})).mark_line(color="red", strokeDash=[4, 4]).encode(x="x", y="y")
    c2.altair_chart(puntos + diag, width="stretch")
    if resumen.get("top5_importancia"):
        st.markdown("**Variables más importantes** (importancia por permutación): " +
                    ", ".join(NOMBRES.get(v, v) for v in resumen["top5_importancia"]))
    st.caption("Validación cruzada de 5 pliegues agrupados por manzana; la prueba (1.796 anuncios) se usó una sola vez."
               + " Cada experimento quedó registrado en MLflow.")

# ---------------------------------------------------------------- simulador
with t_sim:
    st.subheader("¿Cuánto cobraría por noche un apartamento así?")
    st.caption(f"Estimación del modelo {meta['modelo']}. Las variables que no eliges toman el valor típico "
               "(mediana) de los anuncios de la localidad.")
    cat = meta["categorias"]
    c1, c2, c3 = st.columns(3)
    loc = c1.selectbox("Localidad", cat["neighbourhood_cleansed"],
                       index=cat["neighbourhood_cleansed"].index("Chapinero") if "Chapinero" in cat["neighbourhood_cleansed"] else 0)
    tipo = c2.selectbox("Tipo de alojamiento", cat["property_type"],
                        index=cat["property_type"].index("Entire rental unit") if "Entire rental unit" in cat["property_type"] else 0)
    legal = c3.selectbox("Situación frente al RNT", cat["grupo_legal"])
    c1, c2, c3 = st.columns(3)
    huespedes = c1.slider("Huéspedes", 1, 12, 3)
    habitaciones = c2.slider("Habitaciones", 0, 6, 1)
    banos = c3.slider("Baños", 1.0, 5.0, 1.0, 0.5)
    elegidas = st.multiselect("Comodidades", list(AMENIDADES), format_func=AMENIDADES.get,
                              default=["am_wifi", "am_cocina"])

    zona = anuncios[anuncios["neighbourhood_cleansed"] == loc]
    fila = {c: float(zona[c].median()) if len(zona) else meta["medianas"][c] for c in meta["NUM_SEL"]}
    fila.update({c: int(round(zona[c].mean())) if len(zona) else 0 for c in meta["BIN"]})
    fila.update({"accommodates": huespedes, "bedrooms": habitaciones, "banos": banos})
    fila.update({c: int(c in elegidas) for c in AMENIDADES if c in meta["BIN"]})
    fila.update({"neighbourhood_cleansed": loc, "property_type": tipo, "grupo_legal": legal})
    X = pd.DataFrame([fila])[meta["NUM_SEL"] + meta["BIN"] + meta["CAT"]]
    precio = float(np.exp(modelo.predict(X)[0]))
    ref = zona["precio"].median() if len(zona) else anuncios["precio"].median()
    c1, c2 = st.columns(2)
    c1.metric("Precio estimado por noche", cop(precio))
    c2.metric(f"Precio mediano en {loc}", cop(ref), f"{100 * (precio / ref - 1):+.0f} %".replace(".", ","))
    st.caption("El error típico del modelo es de unos ±45.000 COP por noche (MAE en la prueba). Es una estimación, "
               "no una recomendación de precio.")
