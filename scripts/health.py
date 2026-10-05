"""Probe published endpoints with finite timeouts, without credentials."""

import argparse
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--web-url", default="http://localhost:3000")
    parser.add_argument("--worker-url", default="http://localhost:3030")
    parser.add_argument("--minio-url", default="http://localhost:9095")
    args = parser.parse_args()
    probes = {
        "web": args.web_url.rstrip("/") + "/api/public/health",
        "worker": args.worker_url.rstrip("/") + "/api/health",
        "minio": args.minio_url.rstrip("/") + "/minio/health/ready",
    }
    failed = False
    for name, url in probes.items():
        try:
            with urlopen(url, timeout=5) as response:
                ok = response.status == 200
            print(f"{name}: {'OK' if ok else 'FAILED'}")
            failed |= not ok
        except (HTTPError, URLError, TimeoutError, OSError):
            print(f"{name}: FAILED (unreachable or unhealthy)")
            failed = True
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
