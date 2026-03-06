from redis_queue import queue
from rq import Queue

redis_conn = Redis(host="localhost", port=6379)

queue = Queue("ocr_queue", connection=redis_conn)