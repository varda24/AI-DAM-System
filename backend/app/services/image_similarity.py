from pathlib import Path

import imagehash
from PIL import Image


def calculate_perceptual_hash(file_path: str | Path) -> str:
    path = Path(file_path)

    with Image.open(path) as image:
        image = image.convert("RGB")
        perceptual_hash = imagehash.phash(image)

    return str(perceptual_hash)


def hamming_distance(hash_a: str, hash_b: str) -> int:
    return imagehash.hex_to_hash(hash_a) - imagehash.hex_to_hash(hash_b)