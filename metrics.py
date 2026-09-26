
from prometheus_client import Counter, Gauge, Histogram, start_http_server
from config import METRICS_PORT

TASKS_TOTAL = Counter("factory_tasks_total", "Total processed tasks", ["action", "status"])
BOT_EVENTS = Counter("factory_bot_events_total", "Bot lifecycle events", ["event"])
WORKER_LOAD = Gauge("factory_worker_load", "Current worker bot load", ["worker_id"])
TASK_LATENCY = Histogram("factory_task_latency_seconds", "Task processing latency", ["action"])

def start_metrics():
    start_http_server(METRICS_PORT)
