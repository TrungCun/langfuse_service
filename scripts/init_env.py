"""Generate local deployment secrets without overwriting an existing .env."""

from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parents[1]


def initialize(root: Path = ROOT) -> bool:
    target = root / ".env"
    template = (root / ".env.example").read_text(encoding="utf-8")
    lines = []
    for line in template.splitlines():
        if line.endswith("=__GENERATE__"):
            key = line.split("=", 1)[0]
            # Hex is safe in PostgreSQL URLs, Compose and shell arguments.
            line = f"{key}={secrets.token_hex(32)}"
        lines.append(line)
    try:
        with target.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(lines) + "\n")
    except FileExistsError:
        print("Existing .env preserved; no secrets changed.")
        return False
    print("Created .env with random secrets. Do not commit or share this file.")
    return True


if __name__ == "__main__":
    initialize()

