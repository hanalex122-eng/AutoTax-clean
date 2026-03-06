import redis

r = redis.Redis(
    host="localhost",
    port=6379,
    password="autotax_redis_pass",
    decode_responses=True
)

job_id = input("Job ID gir: ")

result = r.get(f"ocr_result:{job_id}")

print("Result:", result) 