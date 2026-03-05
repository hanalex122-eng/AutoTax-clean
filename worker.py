import redis
import time

r = redis.Redis(
    host="localhost",
    port=6379,
    password="autotax_redis_pass",
    decode_responses=True
)

print("Worker started...")

while True:
    job = r.rpop("ocr_queue")

    if job:
        print("Processing:", job)
        time.sleep(2)
        print("Done:", job)

    time.sleep(1)