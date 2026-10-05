"""Update public URLs in an existing .env, preserving every deployment secret."""

import argparse
import ipaddress
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def configure(host: str, root: Path = ROOT):
    address = ipaddress.IPv4Address(host)
    if address.is_loopback or address.is_unspecified or address.is_multicast:
        raise ValueError("Use the actual LAN IPv4 address, not a loopback/bind address")
    path = root / ".env"
    lines = path.read_text(encoding="utf-8").splitlines()
    values = dict(line.split("=", 1) for line in lines if "=" in line and not line.lstrip().startswith("#"))
    web_port = int(values.get("WEB_PORT", "3000"))
    media_port = int(values.get("MINIO_PORT", "9095"))
    if not all(1 <= port <= 65535 for port in (web_port, media_port)):
        raise ValueError("Ports must be between 1 and 65535")
    replacements = {
        "NEXTAUTH_URL": f"http://{address}:{web_port}",
        "MEDIA_PUBLIC_URL": f"http://{address}:{media_port}",
    }
    output = []
    updated = set()
    for line in lines:
        key = line.split("=", 1)[0]
        if key in replacements:
            output.append(f"{key}={replacements[key]}")
            updated.add(key)
        else:
            output.append(line)
    output.extend(f"{key}={value}" for key, value in replacements.items() if key not in updated)
    path.write_text("\n".join(output) + "\n", encoding="utf-8")
    print(f"Web/API: {replacements['NEXTAUTH_URL']}")
    print(f"Media/S3: {replacements['MEDIA_PUBLIC_URL']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="Windows host LAN IPv4 address")
    args = parser.parse_args()
    configure(args.host)
