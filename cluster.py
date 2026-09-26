import json,time,secrets
from redis.asyncio import Redis
from config import REDIS_URL,WORKER_TTL,MAX_BOTS_PER_WORKER,LOCK_TTL
_RELEASE="""if redis.call('get',KEYS[1])==ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end"""
class Cluster:
 def __init__(self,url=REDIS_URL): self.redis=Redis.from_url(url,decode_responses=True)
 async def close(self): await self.redis.aclose()
 async def heartbeat(self,worker_id,load=0):
  await self.redis.set(f'factory:worker:{worker_id}',json.dumps({'worker_id':worker_id,'load':load,'capacity':MAX_BOTS_PER_WORKER,'ts':time.time()}),ex=WORKER_TTL)
 async def workers(self):
  out=[]
  async for key in self.redis.scan_iter(match='factory:worker:*'):
   raw=await self.redis.get(key)
   if raw:
    try: out.append(json.loads(raw))
    except: pass
  return out
 async def choose_worker(self):
  ws=[w for w in await self.workers() if w.get('load',0)<w.get('capacity',MAX_BOTS_PER_WORKER)]
  return min(ws,key=lambda w:w.get('load',0)) if ws else None
 async def assign_bot(self,bot_id,worker_id): await self.redis.set(f'factory:bot:{bot_id}:worker',worker_id)
 async def bot_worker(self,bot_id): return await self.redis.get(f'factory:bot:{bot_id}:worker')
 async def release_bot(self,bot_id): await self.redis.delete(f'factory:bot:{bot_id}:worker')
 async def acquire_lock(self,name):
  token=secrets.token_urlsafe(24); ok=await self.redis.set(f'factory:lock:{name}',token,nx=True,ex=LOCK_TTL)
  return token if ok else None
 async def release_lock(self,name,token): return await self.redis.eval(_RELEASE,1,f'factory:lock:{name}',token)
