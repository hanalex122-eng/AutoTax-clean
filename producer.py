import redis
import json
import uuid
import sys
from pdf2image import convert_from_path

r = redis.Redis(
    host="localhost",
    port=6379,
    password="autotax_redis_pass",
    decode_responses=True
)

if len(sys.argv) < 2:
    print("Usage: python producer.py <file>")
    sys.exit(1)

file_path = sys.argv[1]

jobs_created = []

# PDF ise sayfalara böl
if file_path.lower().endswith(".pdf"):

    pages = convert_from_path(file_path)

    for i, page in enumerate(pages):

        image_path = f"temp_page_{i}.png"
        page.save(image_path, "PNG")

        job_id = str(uuid.uuid4())

        job = {
            "id": job_id,
            "image": image_path
        }

        r.lpush("ocr_queue", json.dumps(job))

        jobs_created.append(job_id)

else:
    # image ise direkt gönder
    job_id = str(uuid.uuid4())

    job = {
        "id": job_id,
        "image": file_path
    }

    r.lpush("ocr_queue", json.dumps(job))

    jobs_created.append(job_id)

print("Jobs created:")
for j in jobs_created:
    print(j)