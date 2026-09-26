import pytest
from task_queue import TaskQueue
class R:
 def __init__(self): self.ready=[]; self.dead=[]
 async def rpush(self,k,v): (self.ready if k.endswith('tasks') else self.dead).append(v)
 async def llen(self,k): return len(self.ready if k.endswith('tasks') else self.dead)
 async def lrange(self,k,*a): return self.dead
 async def lrem(self,*a): return 0
 async def zadd(self,*a): pass
 async def zrangebyscore(self,*a,**k): return []
 async def blpop(self,*a): return None
@pytest.mark.asyncio
async def test_v8_dlq():
 r=R(); q=TaskQueue.__new__(TaskQueue); q.redis=r
 await r.rpush('factory:dead','{"id":"x"}')
 assert await q.dead_depth()==1
