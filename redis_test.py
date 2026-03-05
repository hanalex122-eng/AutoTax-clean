import redis

r = redis.Redis(
    host="localhost",
    port=6379,
    password="autotax_redis_pass",
    decode_responses=True
)

r.set("python_test", "it works")

print(r.get("python_test"))