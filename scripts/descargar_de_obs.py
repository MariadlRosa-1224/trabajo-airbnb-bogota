"""Descarga salidas_app.zip desde OBS y lo descomprime en DATA_DIR.

No usa claves guardadas: pide credenciales temporales al servicio de metadatos de la ECS,
que las entrega gracias a la agencia de IAM asignada a la ECS (ecs-lee-obs, OBS ReadOnlyAccess).

Uso (desde la carpeta del repositorio, en la ECS):
    docker compose run --rm app python scripts/descargar_de_obs.py
"""
import json
import os
import pathlib
import sys
import urllib.request
import zipfile

from obs import ObsClient

METADATOS = "http://169.254.169.254/openstack/latest/securitykey"
ENDPOINT = os.environ["OBS_ENDPOINT"]
BUCKET = os.environ["OBS_BUCKET"]
OBJETO = os.getenv("OBS_OBJETO", "entrada/salidas_app.zip")
DATA = pathlib.Path(os.getenv("DATA_DIR", "/data"))


def credenciales_temporales():
    try:
        with urllib.request.urlopen(METADATOS, timeout=5) as r:
            return json.load(r)["credential"]
    except Exception as e:
        sys.exit(f"No se obtuvieron credenciales temporales ({e}).\n"
                 "¿La ECS tiene asignada la agencia ecs-lee-obs? "
                 "Alternativa: descarga el zip desde la consola de OBS y cópialo a data/.")


def main():
    cred = credenciales_temporales()
    cliente = ObsClient(access_key_id=cred["access"], secret_access_key=cred["secret"],
                        security_token=cred["securitytoken"], server=f"https://{ENDPOINT}")
    DATA.mkdir(parents=True, exist_ok=True)
    destino = DATA / "salidas_app.zip"
    resp = cliente.getObject(BUCKET, OBJETO, downloadPath=str(destino))
    cliente.close()
    if resp.status >= 300:
        sys.exit(f"OBS respondió {resp.status}: {resp.errorCode} {resp.errorMessage}")

    with zipfile.ZipFile(destino) as z:
        z.extractall(DATA)
    print(f"Descargado {OBJETO} ({destino.stat().st_size / 1e6:.1f} MB) y descomprimido en {DATA}:")
    for p in sorted(DATA.iterdir()):
        print("  ·", p.name)


if __name__ == "__main__":
    main()
