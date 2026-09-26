
import json, time
from redis.asyncio import Redis
from config import REDIS_URL, TASK_MAX_RETRIES, RETRY_BASE_SECONDS

class TaskQueue:
    def __init__(self, url=REDIS_URL):
        self.redis = Redis.from_url(url, decode_responses=True)

    async def close(self):
        await self.redis.aclose()

    async def enqueue(self, action, bot_id, retry=0, delay=0, reason=None):
        task = {
            "id": f"{action}:{bot_id}:{time.time_ns()}",
            "action": action,
            "bot_id": int(bot_id),
            "retry": int(retry),
            "reason": reason,
            "created_at": time.time(),
        }
        if delay:
            await self.redis.zadd("factory:delayed", {json.dumps(task): time.time() + delay})
        else:
            await self.redis.rpush("factory:tasks", json.dumps(task))
        return task["id"]

    async def promote_delayed(self):
        now = time.time()
        items = await self.redis.zrangebyscore("factory:delayed", 0, now, start=0, num=100)
        if not items:
            return 0
        for raw in items:
            await self.redis.rpush("factory:tasks", raw)
            await self.redis.zrem("factory:delayed", raw)
        return len(items)

    async def next_task(self, timeout=5):
        await self.promote_delayed()
        item = await self.redis.blpop("factory:tasks", timeout=timeout)
        if not item:
            return None
        return json.loads(item[1])

    async def dead_list(self, limit=100):
        items = await self.redis.lrange("factory:dead", 0, max(0, limit-1))
        return [json.loads(x) for x in items]

    async def dead_retry(self, task_id):
        for raw in await self.redis.lrange("factory:dead", 0, -1):
            item=json.loads(raw)
            if item.get("id")==task_id:
                await self.redis.lrem("factory:dead", 1, raw)
                await self.enqueue(item["action"], item["bot_id"], retry=0, reason="manual DLQ retry")
                return True
        return False

    async def dead_delete(self, task_id):
        for raw in await self.redis.lrange("factory:dead", 0, -1):
            if json.loads(raw).get("id")==task_id:
                await self.redis.lrem("factory:dead", 1, raw); return True
        return False

    async def depth(self): return await self.redis.llen("factory:tasks")
    async def dead_depth(self): return await self.redis.llen("factory:dead")

    async def fail(self, task, error):
        retry = int(task.get("retry", 0)) + 1
        if retry > TASK_MAX_RETRIES:
            task["error"] = str(error)
            task["failed_at"] = time.time()
            await self.redis.rpush("factory:dead", json.dumps(task))
            return False
        delay = RETRY_BASE_SECONDS * (2 ** (retry - 1))
        await self.enqueue(task["action"], task["bot_id"], retry=retry, delay=delay, reason=str(error))
        return True
