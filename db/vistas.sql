-- Vistas agregadas sobre la tabla anuncios. Las usan Metabase y Streamlit,
-- así los números coinciden en las dos herramientas.
-- Precios en COP por noche; valor del suelo en COP/m²; brecha solo con anuncios activos (como la Tabla IV).

CREATE OR REPLACE VIEW v_localidad AS
SELECT neighbourhood_cleansed                                              AS localidad,
       COUNT(*)                                                            AS anuncios,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY precio)                 AS precio_mediano,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY valor_suelo_m2_w)       AS valor_suelo_mediano,
       ROUND(100.0 * AVG(CASE WHEN grupo_legal = 'RNT activo Bogotá' THEN 1 ELSE 0 END), 1) AS pct_rnt_activo
FROM anuncios
GROUP BY neighbourhood_cleansed;

CREATE OR REPLACE VIEW v_legalidad AS
SELECT grupo_legal,
       COUNT(*)                                                            AS anuncios,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)                  AS pct_anuncios,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY precio)                 AS precio_mediano
FROM anuncios
GROUP BY grupo_legal;

CREATE OR REPLACE VIEW v_quintil AS
SELECT quintil_suelo,
       COUNT(*)                                                            AS anuncios,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY valor_suelo_m2_w)       AS valor_suelo_mediano,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY precio)                 AS precio_mediano,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY brecha_renta) FILTER (WHERE activo = 1) AS brecha_mediana
FROM anuncios
GROUP BY quintil_suelo;

CREATE OR REPLACE VIEW v_estrato AS
SELECT estrato,
       COUNT(*)                                                            AS anuncios,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY precio)                 AS precio_mediano,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY brecha_renta) FILTER (WHERE activo = 1) AS brecha_mediana
FROM anuncios
WHERE estrato IS NOT NULL
GROUP BY estrato;

CREATE OR REPLACE VIEW v_modelos AS
SELECT *
FROM metricas_modelos
ORDER BY rmse_log;
