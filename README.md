# Airbnb en Bogotá: precio, valor de la propiedad y legalidad

Implementación del proyecto final de Analítica de Datos en **Huawei Cloud**.
El análisis y los modelos se hacen en Kaggle (notebook `p final`); esta carpeta despliega los resultados.

```
Kaggle (secciones 4–8) ──► OBS  entrada/salidas_app.zip
                              │  (la ECS lo lee con la agencia ecs-lee-obs: sin claves guardadas)
                              ▼
ECS (subnet-app, sg-app, EIP) ── docker compose
  ├ app       Streamlit  :8501  ─┐
  ├ metabase  Metabase   :3000  ─┼──► RDS for PostgreSQL (subnet-db, sg-db)
  └ mlflow    MLflow UI  :5000   │      bases: airbnb (datos)  ·  metabase (configuración)
```

| Carpeta / archivo | Qué es |
|---|---|
| `app/app.py` | App de Streamlit: Resumen, Mapa, Hipótesis, Modelos y Simulador de precio |
| `app/resumen_modelos.json` | Resultados de H1, H2 y modelos (sale de `salidas_seccion7.zip`) |
| `scripts/descargar_de_obs.py` | Descarga y descomprime `salidas_app.zip` desde OBS en `data/` |
| `scripts/cargar_postgres.py` | Crea las tablas `anuncios`, `predicciones`, `metricas_modelos` y las vistas en RDS |
| `db/vistas.sql` | Vistas por localidad, legalidad, quintil, estrato y modelos (las usan Metabase y Streamlit) |
| `docker-compose.yml` | Los tres servicios; la configuración sale de `.env` |

## Fase 4 – Desplegar en la ECS

### 1. Crear la ECS (consola → ECS → Buy ECS)
- **Billing:** pay-per-use · **Región:** la misma de la VPC y la RDS
- **Flavor:** uso general, **2 vCPU / 4 GiB** (Metabase necesita ~1,5 GB de memoria)
- **Imagen:** Ubuntu 24.04 · **Disco del sistema:** 40 GB
- **Red:** `vpc-trabajo-airbnb`, `subnet-app` · **Security group:** `sg-app`
- **EIP:** nueva, **cobrada por tráfico**, 5 Mbit/s
- **Agencia (Management Information):** `ecs-lee-obs` (si no aparece, se asigna después desde la cuenta principal)
- **Login:** contraseña o key pair

### 2. Preparar la ECS
Conéctate por SSH (`ssh root@<EIP>`) y ejecuta:
```bash
curl -fsSL https://get.docker.com | sh          # instala Docker y docker compose
git clone https://github.com/<tu-usuario>/proyecto-airbnb-bogota.git
cd proyecto-airbnb-bogota
cp .env.example .env && nano .env               # completa OBS, RDS (IP privada) y EIP
```

### 3. Levantar los servicios y cargar los datos
```bash
docker compose build                                         # la primera vez tarda unos minutos
docker compose run --rm app python scripts/descargar_de_obs.py   # OBS → data/
docker compose run --rm app python scripts/cargar_postgres.py    # data/ → RDS (tablas + vistas)
docker compose up -d                                         # Streamlit, Metabase y MLflow
docker compose ps                                            # los tres deben decir "running"
```
- Streamlit: `http://<EIP>:8501` · Metabase: `http://<EIP>:3000` · MLflow: `http://<EIP>:5000`
- Si `descargar_de_obs.py` falla por la agencia: descarga el zip desde la consola de OBS, cópialo con
  `scp salidas_app.zip root@<EIP>:proyecto-airbnb-bogota/data/` y descomprímelo con `unzip` dentro de `data/`.

### 4. Metabase (con clics)
1. Abre `http://<EIP>:3000` y crea la cuenta de administrador.
2. **Add database → PostgreSQL:** host = IP privada de la RDS, puerto 5432, base `airbnb`, usuario `root`.
3. Crea preguntas sobre las vistas `v_localidad`, `v_legalidad`, `v_quintil`, `v_estrato`, `v_modelos` y la tabla `anuncios` (mapa de puntos con latitude/longitude), y júntalas en un dashboard.
4. Para la clase: **Admin → Settings → Public sharing → activar**; en el dashboard, ícono de compartir → enlace público.

### 5. Abrir la app a la clase (solo el día de la presentación)
En `sg-app`, agrega reglas de entrada TCP **8501** y **3000** desde `0.0.0.0/0`.
**MLflow (5000) queda solo para tu IP:** no tiene usuario ni contraseña.

### Actualizar los datos
Vuelve a exportar desde Kaggle, sube el zip a OBS y ejecuta otra vez los dos scripts del paso 3 y
`docker compose restart app`. Si cambian los resultados de la sección 7, reemplaza `app/resumen_modelos.json`.

## Al terminar (después de la presentación)
Borra la ECS (marcando liberar EIP y disco) y la RDS (encendida). El bucket de OBS y la VPC no cobran casi nada.

## Versiones importantes
- `scikit-learn==1.6.1`: es la versión con la que Kaggle guardó el modelo; con otra no carga.
- `mlflow==3.18.0`: la base `mlflow.db` exportada usa el esquema de esa versión.
- La carpeta `data/` se monta en MLflow como `/kaggle/working/proyecto_airbnb`, la misma ruta que en Kaggle,
  para que las gráficas registradas (artefactos) se vean en la interfaz.
