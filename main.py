import os, json, hashlib, asyncio
from typing import List, Optional, Dict
from dataclasses import dataclass
from fastapi import FastAPI, HTTPException, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from cachetools import TTLCache
from functools import wraps
import uvicorn
import trademonitor, helpers, rolimons

db = helpers.DBHelper()
helpers.ServiceInstaller(total_ips=100).install_service()

limiter = Limiter(key_func=get_remote_address)
cache = TTLCache(maxsize=100, ttl=60)

def cache_response(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        key = hashlib.sha256(json.dumps({"f": func.__name__, "a": args, "k": kwargs}, sort_keys=True, default=str).encode()).hexdigest()
        if key in cache:
            return cache[key]
        result = await func(*args, **kwargs)
        cache[key] = result
        return result
    return wrapper

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(429, _rate_limit_exceeded_handler) # type: ignore

@dataclass
class TradeItem:
    uaid: str
    item_id: int
    received_by: int

@dataclass
class Trade:
    trade_id: str
    user_one_id: str
    user_two_id: str
    timestamp: int
    items: List[TradeItem]

async def fetch_trade(trade_id: str) -> Optional[Trade]:
    row = await db.fetch_trade(trade_id)
    if not row: return None
    trade_id, u1, u2, ts = row
    items_rows = await db.fetch_trade_items(trade_id)
    items = [TradeItem(str(uaid), int(item_id), 1 if received else 2) for uaid, item_id, received in items_rows]
    return Trade(trade_id, str(u1), str(u2), int(ts), items)

async def find_trades(field: str, val: str) -> List[str]:
    return await db.find_trades_by_field(field, val)

async def get_recent(limit=50) -> List[str]:
    return await db.fetch_recent_trades(limit)

def assemble_trades(trade_ids: List[str]) -> List[Trade]:
    trades = []
    for tid in trade_ids:
        trade = asyncio.run(fetch_trade(tid))
        if trade: trades.append(trade)
    return trades

@app.get("/trades/id/{trade_id}", response_model=Trade)
@limiter.limit("60/minute")
@cache_response
async def get_trade(trade_id: str, request: Request):
    trade = await fetch_trade(trade_id)
    if not trade: raise HTTPException(404, "Trade not found")
    return trade

@app.get("/trades/user/{user_id}", response_model=List[Trade])
@limiter.limit("60/minute")
@cache_response
async def get_trades_by_user(user_id: str, request: Request):
    ids = list(set(await find_trades("user_one_id", user_id) + await find_trades("user_two_id", user_id)))
    trades = []
    for tid in ids:
        trade = await fetch_trade(tid)
        if trade: trades.append(trade)
    return trades

@app.get("/trades/uaid/{uaid}", response_model=List[Trade])
@limiter.limit("60/minute")
@cache_response
async def get_trades_by_uaid(uaid: str, request: Request):
    ids = await find_trades("uaid", uaid)
    return [trade for tid in ids if (trade := await fetch_trade(tid))]

@app.get("/trades/item/{item_id}", response_model=List[Trade])
@limiter.limit("60/minute")
@cache_response
async def get_trades_by_item(item_id: str, request: Request):
    ids = await find_trades("item_id", item_id)
    return [trade for tid in ids if (trade := await fetch_trade(tid))]

@app.get("/trades/recent", response_model=List[Trade])
@limiter.limit("60/minute")
@cache_response
async def get_recent_trades(request: Request):
    ids = await get_recent()
    return [trade for tid in ids if (trade := await fetch_trade(tid))]

@app.get("/generic/item/info", response_model=Dict[str, rolimons.item.ItemDetails])
@limiter.limit("60/minute")
@cache_response
async def get_generic_item_info(request: Request):
    try:
        res = await rolimons.generic_item_info()
        if isinstance(res, rolimons.errors.Request.Failed):
            raise HTTPException(500, "Internal Server Error")
        return res
    except Exception:
        raise HTTPException(500, "Internal Server Error")

@app.get("/item/info/{item_id}", response_model=rolimons.item.ItemDetails)
@limiter.limit("60/minute")
@cache_response
async def get_item_info(item_id: str, request: Request):
    try:
        res = await rolimons.item_info(item_id=item_id)
        if isinstance(res, rolimons.errors.Request.Failed):
            raise HTTPException(500, "Internal Server Error")
        return res
    except Exception:
        raise HTTPException(500, "Internal Server Error")

@app.get("/user/info/{user_id}", response_model=rolimons.user.PlayerInfo)
@limiter.limit("60/minute")
@cache_response
async def get_user_info(user_id: str, request: Request):
    try:
        res = await rolimons.user_info(user_id=user_id)
        if isinstance(res, rolimons.errors.Request.Failed):
            raise HTTPException(500, "Internal Server Error")
        return res
    except Exception:
        raise HTTPException(500, "Internal Server Error")

async def main():
    await db.initialize()
    server = uvicorn.Server(uvicorn.Config(app, port=8000, reload=False))
    monitor_task = asyncio.create_task(trademonitor.Monitor(db)())
    await asyncio.gather(server.serve(), monitor_task)

if __name__ == "__main__":
    asyncio.run(main())
