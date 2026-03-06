import redis
import json
import time
from paddleocr import PaddleOCR

# Redis bağlantısı
r = redis.Redis(
    host="localhost",
    port=6379,
    password="autotax_redis_pass",
    decode_responses=True
)

# OCR modeli
ocr = PaddleOCR(use_angle_cls=True, lang="en")

print("OCR Worker started...")

while True:

    # queue'dan job al
    job = r.rpop("ocr_queue")

    if job:
        job_data = json.loads(job)

        job_id = job_data["id"]
        image_path = job_data["image"]

        print("Processing job:", job_id)

        try:
            result = ocr.ocr(image_path)

            texts = []
            for line in result:
                for word in line:
                    texts.append(word[1][0])

            text_result = " ".join(texts)

            # sonucu kaydet
            r.set(f"ocr_result:{job_id}", text_result)

            print("Done:", job_id)

        except Exception as e:
            r.set(f"ocr_result:{job_id}", f"error: {str(e)}")

    time.sleep(1)