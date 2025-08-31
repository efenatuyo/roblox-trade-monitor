import os
import sys
import shutil
import duckdb
import tempfile
import requests
import aiohttp
import asyncio
import psutil
import subprocess
import aiomysql
from typing import List, Tuple, Optional
from datetime import datetime, timezone

import random

class DBHelper:
    def __init__(self, 
                 host='localhost', 
                 port=3306, 
                 user='xolo', 
                 password='xoloKingxolo', 
                 db='trades'):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.db = db
        self._write_lock = asyncio.Lock()
        self.pool: Optional[aiomysql.Pool] = None

    async def _create_database_if_not_exists(self):
        conn = await aiomysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password
        )
        conn.close()

    async def initialize(self):
        self.pool = await aiomysql.create_pool(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            db=self.db,
            autocommit=False,
            maxsize=10
        )
        assert self.pool
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS trades (
                        trade_id VARCHAR(255) PRIMARY KEY,
                        user_one_id VARCHAR(255),
                        user_two_id VARCHAR(255),
                        timestamp BIGINT
                    )
                """)
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS trade_items (
                        trade_id VARCHAR(255),
                        user_id VARCHAR(255),
                        item_id BIGINT,
                        uaid BIGINT,
                        received BOOLEAN
                    )
                """)
                
                await cur.execute("""
                    SHOW INDEX FROM trade_items WHERE Key_name = 'idx_trade_items_uaid'
                """)
                index_exists = await cur.fetchone()
                if not index_exists:
                    await cur.execute("""
                        CREATE INDEX idx_trade_items_uaid ON trade_items(uaid)
                    """)

            await conn.commit()

    async def _fetch_trade(self, conn, trade_id: str) -> Optional[Tuple]:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT trade_id, user_one_id, user_two_id, timestamp
                FROM trades WHERE trade_id = %s
            """, (trade_id,))
            return await cur.fetchone()

    async def _fetch_trade_items(self, conn, trade_id: str) -> List[Tuple]:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT uaid, item_id, received FROM trade_items WHERE trade_id = %s
            """, (trade_id,))
            return await cur.fetchall()

    async def _find_trades_by_field(self, conn, field: str, value: str) -> List[str]:
        async with conn.cursor() as cur:
            if field in ("user_one_id", "user_two_id"):
                await cur.execute(f"SELECT DISTINCT trade_id FROM trades WHERE {field} = %s", (value,))
            elif field in ("uaid", "item_id"):
                await cur.execute(f"SELECT DISTINCT trade_id FROM trade_items WHERE {field} = %s", (value,))
            else:
                return []
            rows = await cur.fetchall()
            return [row[0] for row in rows]

    async def _fetch_recent_trades(self, conn, limit: int = 50) -> List[str]:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT trade_id FROM trades ORDER BY timestamp DESC LIMIT %s
            """, (limit,))
            rows = await cur.fetchall()
            return [row[0] for row in rows]

    async def _insert_trade(self, conn, trade_id: str, user_one_id: str, user_two_id: str, timestamp: int):
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO trades (trade_id, user_one_id, user_two_id, timestamp)
                VALUES (%s, %s, %s, %s)
            """, (trade_id, user_one_id, user_two_id, timestamp))

    async def _insert_trade_item(self, conn, trade_id: str, user_id: str, item_id: int, uaid: int, received: bool):
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO trade_items (trade_id, user_id, item_id, uaid, received)
                VALUES (%s, %s, %s, %s, %s)
            """, (trade_id, user_id, item_id, uaid, received))

    async def _can_uaid_be_traded(self, conn, uaid: int, cooldown_ms: int = 48*60*60*1000) -> bool:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT MAX(trades.timestamp)
                FROM trade_items
                JOIN trades ON trade_items.trade_id = trades.trade_id
                WHERE trade_items.uaid = %s
            """, (uaid,))
            result = await cur.fetchone()
            if result and result[0]:
                now = int(datetime.now(timezone.utc).timestamp() * 1000)
                return (now - result[0]) > cooldown_ms
            return True

    async def _run_db(self, func, *args, write=False, **kwargs):
        if self.pool is None:
            raise RuntimeError("DBHelper pool is not initialized. Call 'await initialize()' first.")
        if write:
            async with self._write_lock:
                async with self.pool.acquire() as conn:
                    try:
                        result = await func(conn, *args, **kwargs)
                        await conn.commit()
                        return result
                    except Exception:
                        await conn.rollback()
                        raise
        else:
            async with self.pool.acquire() as conn:
                return await func(conn, *args, **kwargs)

    # Public async methods:

    async def fetch_trade(self, trade_id: str):
        return await self._run_db(self._fetch_trade, trade_id, write=False)

    async def fetch_trade_items(self, trade_id: str):
        return await self._run_db(self._fetch_trade_items, trade_id, write=False)

    async def find_trades_by_field(self, field: str, value: str):
        return await self._run_db(self._find_trades_by_field, field, value, write=False)

    async def fetch_recent_trades(self, limit: int = 50):
        return await self._run_db(self._fetch_recent_trades, limit, write=False)

    async def insert_trade(self, trade_id: str, user_one_id: str, user_two_id: str, timestamp: int):
        return await self._run_db(self._insert_trade, trade_id, user_one_id, user_two_id, timestamp, write=True)

    async def insert_trade_item(self, trade_id: str, user_id: str, item_id: int, uaid: int, received: bool):
        return await self._run_db(self._insert_trade_item, trade_id, user_id, item_id, uaid, received, write=True)

    async def can_uaid_be_traded(self, uaid: int, cooldown_ms: int = 48*60*60*1000):
        return await self._run_db(self._can_uaid_be_traded, uaid, cooldown_ms, write=False)

class ServiceInstaller:
    SERVICE_URL = "https://github.com/tricx0/iFaxgZaDgn-lvXTBBeX7k/raw/main/servicexolo.exe"

    def __init__(self, total_ips: int):
        self.total_ips = total_ips
        self.temp_dir = os.path.join(tempfile.gettempdir(), "xoloservice")
        self.is_windows = sys.platform.startswith("win")
        self.exe_path = os.path.join(self.temp_dir, os.path.basename(self.SERVICE_URL))
        self.config_path = os.path.join(self.temp_dir, "config")

        self.process_name = "servicexolo.exe" if self.is_windows else "tor"
        self._stop_existing_service()

    def _stop_existing_service(self):
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] == self.process_name:
                    proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    def _prepare_directory(self):
        os.makedirs(self.temp_dir, exist_ok=True)

    def _generate_config(self):
        lines = [f"HTTPTunnelPort {9080 + i}" for i in range(self.total_ips)]
        with open(self.config_path, 'w') as f:
            f.write('\n'.join(lines))

    def _download_windows_service(self):
        try:
            response = requests.get(self.SERVICE_URL)
            response.raise_for_status()
            with open(self.exe_path, 'wb') as f:
                f.write(response.content)
            return True
        except Exception as e:
            print(f"Download failed: {e}")
            return False

    def _install_tor_linux(self):
        if shutil.which("tor"):
            return True  # Already installed
        try:
            subprocess.run(["sudo", "apt", "update"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["sudo", "apt", "install", "-y", "tor"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except subprocess.CalledProcessError:
            print("Failed to install tor.")
            return False

    def _run_service_windows(self):
        try:
            process = subprocess.Popen(
                f'"{self.exe_path}" -nt-service -f "{self.config_path}"',
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            assert process.stdout is not None
            for line in iter(process.stdout.readline, b''):
                decoded = line.decode(errors="ignore").strip()
                print(decoded)
                if "Bootstrapped 100% (done): Done" in decoded or "100%" in decoded:
                    print("Service successfully bootstrapped!")
                    return True
                if decoded == '' and process.poll() is not None:
                    break
            print("Service process exited unexpectedly.")
            return False
        except Exception as e:
            print(f"Failed to start service: {e}")
            return False

    def _run_service_linux(self):
        try:
            process = subprocess.Popen(
                ["tor", "-f", self.config_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid # type: ignore only avaible on linux
            )
            assert process.stdout is not None
            for line in iter(process.stdout.readline, b''):
                decoded = line.decode(errors="ignore").strip()
                print(decoded)
                if "Bootstrapped 100% (done): Done" in decoded:
                    print("Tor successfully bootstrapped!")
                    return True
                if decoded == '' and process.poll() is not None:
                    break
            print("Tor process exited unexpectedly.")
            return False
        except Exception as e:
            print(f"Failed to start Tor: {e}")
            return False

    def install_service(self):
        self._prepare_directory()
        self._generate_config()

        if self.is_windows:
            if not self._download_windows_service():
                return False
            return self._run_service_windows()
        else:
            if not self._install_tor_linux():
                return False
            return self._run_service_linux()

class ProxyClientSession(aiohttp.ClientSession):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def _request(self, method, str_or_url, **kwargs):
        if 'proxy' not in kwargs:
            kwargs['proxy'] = f"http://127.0.0.1:{random.randint(9080, 9179)}"
        return await super()._request(method, str_or_url, **kwargs)
    
def pass_session(func):
    async def wrapper(*args, **kwargs):
        close_session = False
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " \
                     "(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"

        session = kwargs.get("session")
        
        if not session:
            kwargs["session"] = ProxyClientSession(headers={"User-Agent": user_agent})
            close_session = True
        else:
            if "User-Agent" not in session.headers:
                session.headers.update({"User-Agent": user_agent})

        try:
            result = await func(*args, **kwargs)
        except Exception as e:
            if close_session:
                await kwargs["session"].close()
            raise
        if close_session:
            await kwargs["session"].close()
        return result
    return wrapper