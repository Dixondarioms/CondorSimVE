"""Genera un certificado TLS autofirmado para usar HTTPS en la red local.

    python -m app.gen_cert [--host nombre-o-ip ...]

Incluye localhost, 127.0.0.1, el nombre del equipo y las IP locales detectadas. Los
navegadores mostraran una advertencia hasta que se instale cert.pem como
certificado de confianza en cada equipo (o se use un proxy con un certificado propio).
"""

import argparse
import datetime
import ipaddress
import socket
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from app.db import BASE_DIR

CERTS = BASE_DIR / "certs"


def ips_locales() -> set[str]:
    ips = {"127.0.0.1"}
    try:
        ips.update(i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET))
    except OSError:
        pass
    try:  # IP de la interfaz por defecto (no envia trafico: solo elige la ruta)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            ips.add(s.getsockname()[0])
    except OSError:
        pass
    return ips


def generar(extra: list[str] | None = None, destino: Path = CERTS, dias: int = 730) -> tuple[Path, Path]:
    destino.mkdir(parents=True, exist_ok=True)
    nombres = {"localhost", socket.gethostname()}
    ips = ips_locales() | {"::1"}
    for h in extra or []:
        try:
            ipaddress.ip_address(h)
            ips.add(h)
        except ValueError:
            nombres.add(h)

    clave = ec.generate_private_key(ec.SECP256R1())
    sujeto = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Simulador de Conduccion")])
    ahora = datetime.datetime.now(datetime.timezone.utc)
    alt = [x509.DNSName(n) for n in sorted(nombres)] + [x509.IPAddress(ipaddress.ip_address(i)) for i in sorted(ips)]
    cert = (
        x509.CertificateBuilder()
        .subject_name(sujeto).issuer_name(sujeto).public_key(clave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(ahora - datetime.timedelta(minutes=5))
        .not_valid_after(ahora + datetime.timedelta(days=dias))
        .add_extension(x509.SubjectAlternativeName(alt), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(clave, hashes.SHA256())
    )
    ruta_cert, ruta_clave = destino / "cert.pem", destino / "key.pem"
    ruta_cert.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    ruta_clave.write_bytes(clave.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return ruta_cert, ruta_clave


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", action="append", default=[], help="nombre o IP adicional (repetible)")
    args = ap.parse_args()
    cert, clave = generar(args.host)
    print(f"Certificado: {cert}\nClave privada: {clave} (no la comparta)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
