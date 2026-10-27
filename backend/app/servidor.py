"""Arranca el simulador.

    python -m app.servidor [--host 0.0.0.0] [--port 8001] [--https]

--https usa certs/cert.pem y certs/key.pem (los genera si no existen; ver app.gen_cert).
Detras de un proxy TLS (Caddy, nginx) use --proxy y no --https.
"""

import argparse
import os
import sys


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="127.0.0.1", help="0.0.0.0 para aceptar conexiones de la red local")
    ap.add_argument("--port", type=int, default=8001)
    ap.add_argument("--https", action="store_true")
    ap.add_argument("--proxy", action="store_true", help="confiar en X-Forwarded-* de un proxy inverso")
    args = ap.parse_args()

    opciones = {}
    if args.https:
        from app.gen_cert import CERTS, generar

        cert, clave = CERTS / "cert.pem", CERTS / "key.pem"
        if not (cert.exists() and clave.exists()):
            cert, clave = generar()
            print(f"Certificado autofirmado generado en {cert.parent}")
        opciones = {"ssl_certfile": str(cert), "ssl_keyfile": str(clave)}
    if args.https or args.proxy:
        os.environ["SIMULADOR_COOKIE_SECURE"] = "1"
    if args.proxy:
        opciones.update(proxy_headers=True, forwarded_allow_ips="127.0.0.1")

    import uvicorn

    uvicorn.run("app.main:app", host=args.host, port=args.port, **opciones)
    return 0


if __name__ == "__main__":
    sys.exit(main())
