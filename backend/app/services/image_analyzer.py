from pathlib import Path
from time import perf_counter

import torch
from PIL import Image
from transformers import BlipForConditionalGeneration, BlipProcessor

MODEL_NAME = "Salesforce/blip-image-captioning-base"


class ImageAnalyzer:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.processor = BlipProcessor.from_pretrained(MODEL_NAME)
        self.model = BlipForConditionalGeneration.from_pretrained(MODEL_NAME)
        self.model.to(self.device)
        self.model.eval()

    def analyze(self, file_path: str | Path) -> dict:
        path = Path(file_path)
        start = perf_counter()

        with Image.open(path) as image:
            image = image.convert("RGB")
            inputs = self.processor(images=image, return_tensors="pt")
            inputs = {key: value.to(self.device) for key, value in inputs.items()}

            with torch.no_grad():
                output = self.model.generate(**inputs, max_new_tokens=40)

            caption = self.processor.decode(output[0], skip_special_tokens=True).strip()

        elapsed_ms = int((perf_counter() - start) * 1000)
        category = self._infer_category(caption)
        tags = self._infer_tags(caption)

        return {
            "caption": caption,
            "category": category,
            "tags": tags,
            "model_name": MODEL_NAME,
            "processing_time_ms": elapsed_ms,
        }

    @staticmethod
    def _infer_category(caption: str) -> str:
        text = caption.lower()
        rules = {
            "person": ["person", "people", "man", "woman", "boy", "girl", "child"],
            "animal": ["dog", "cat", "bird", "horse", "animal"],
            "food": ["food", "pizza", "cake", "meal", "dish", "plate", "restaurant"],
            "nature": ["tree", "forest", "mountain", "beach", "ocean", "lake", "flower", "landscape"],
            "vehicle": ["car", "bus", "truck", "motorcycle", "bike", "vehicle"],
            "building": ["building", "house", "office", "room", "street"],
        }
        for category, keywords in rules.items():
            if any(keyword in text for keyword in keywords):
                return category
        return "other"

    @staticmethod
    def _infer_tags(caption: str) -> str:
        text = caption.lower()
        possible_tags = ["person", "people", "man", "woman", "child", "dog", "cat", "bird", "car", "vehicle", "food", "cake", "pizza", "nature", "tree", "mountain", "beach", "ocean", "building", "house", "room", "street"]
        found = [tag for tag in possible_tags if tag in text]
        return ",".join(dict.fromkeys(found)) if found else ""


_analyzer: ImageAnalyzer | None = None


def get_image_analyzer() -> ImageAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = ImageAnalyzer()
    return _analyzer