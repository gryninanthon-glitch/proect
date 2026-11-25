# make_certs.py
import socket
from datetime import datetime, timedelta
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import ipaddress


def get_local_ip():
    """Определяет IP-адрес компьютера в локальной сети.
    Работает даже без интернета (использует UDP-сокет)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Подключаемся к «внешнему» адресу, но пакет не отправляем.
        # Так ОС выбирает интерфейс по умолчанию (Wi-Fi/Ethernet).
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def generate_self_signed_cert():
    local_ip = get_local_ip()
    print(f"Локальный IP: {local_ip}")

    # Генерируем приватный ключ
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # Настройки сертификата
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u"RU"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"Sozvezdie"),
        x509.NameAttribute(NameOID.COMMON_NAME, u"localhost"),
    ])

    # SAN: localhost + 127.0.0.1 + реальный локальный IP
    san = [
        x509.DNSName(u"localhost"),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
        x509.IPAddress(ipaddress.IPv4Address(local_ip)),
    ]

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow())
        .not_valid_after(datetime.utcnow() + timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName(san),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    # Сохраняем приватный ключ в файл key.pem
    with open("key.pem", "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))

    # Сохраняем сам сертификат в файл cert.pem
    with open("cert.pem", "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    print("✅ Сертификаты key.pem и cert.pem созданы.")
    print(f"Доступ:")
    print(f"  - локально:   https://localhost:8000")
    print(f"  - по IP:      https://{local_ip}:8000")
    print(f"  - по IP:      https://127.0.0.1:8000")


if __name__ == "__main__":
    generate_self_signed_cert()