import os
from paddleocr import PaddleOCR

# OCR model
ocr = PaddleOCR(
    use_textline_orientation=True,
    lang="en"
)

def process_image(image_path):

    result = ocr.ocr(image_path)

    texts = []

    for line in result:
        for word in line:
            texts.append(word[1][0])

    return " ".join(texts)


def process_folder(folder):

    files = os.listdir(folder)

    for file in files:

        if file.lower().endswith((".png", ".jpg", ".jpeg")):

            path = os.path.join(folder, file)

            print("\n====================")
            print("FILE:", file)
            print("====================")

            text = process_image(path)

            print(text)


if __name__ == "__main__":

    process_folder(r"C:\Users\alex-\Desktop\fatura")