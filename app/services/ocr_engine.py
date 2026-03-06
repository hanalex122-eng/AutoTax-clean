import pytesseract
from PIL import Image
import io

from paddleocr import PaddleOCR

from app.config import settings

pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

LANG   = settings.OCR_LANG
CONFIG = "--oem 1 --psm 6"

# PaddleOCR modeli (yüklenmesi biraz zaman alır ama sonra cache olur)
paddle = PaddleOCR(
    use_angle_cls=True,
    lang="en",
    show_log=False
)


def run_paddle(img: Image.Image) -> str:
    try:
        result = paddle.ocr(img, cls=True)
        lines = []

        for line in result:
            for word in line:
                text = word[1][0]
                lines.append(text)

        return "\n".join(lines)

    except Exception:
        return ""


def run_tesseract(img: Image.Image) -> str:

    text = pytesseract.image_to_string(img, lang=LANG, config=CONFIG)

    if len(text.strip()) < 20:
        text = pytesseract.image_to_string(
            img,
            lang=LANG,
            config="--oem 1 --psm 11"
        )

    return text or ""


def run_ocr(png_bytes: bytes) -> str:

    img = Image.open(io.BytesIO(png_bytes))

    # 1️⃣ PaddleOCR dene
    text = run_paddle(img)

    # 2️⃣ Eğer başarısızsa Tesseract fallback
    if len(text.strip()) < 20:
        text = run_tesseract(img)

    return text