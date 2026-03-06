import multiprocessing
multiprocessing.set_start_method("spawn", force=True)


from paddleocr import PaddleOCR
import cv2

ocr = PaddleOCR(use_angle_cls=True, lang="en")

def process_image(image_path):

    result = ocr.ocr(image_path)

    texts = []
    for line in result:
        for word in line:
            texts.append(word[1][0])

    return " ".join(texts)