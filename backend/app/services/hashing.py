import hashlib
from pathlib import Path

CHUNK_SIZE = 1024 * 1024


def calculate_sha256(file_path: str | Path) -> str:
    path = Path(file_path)

    sha256 = hashlib.sha256()

    with path.open("rb") as file:
        while chunk := file.read(CHUNK_SIZE):
            sha256.update(chunk)

    return sha256.hexdigest()