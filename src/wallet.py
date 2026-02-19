"""Async client for the Chia Wallet RPC over HTTPS with mutual TLS."""

import asyncio
import logging
import ssl
from typing import Any

import httpx

from .config import (
    WALLET_CERT,
    WALLET_KEY,
    WALLET_RPC_HOST,
    WALLET_RPC_PORT,
)

logger = logging.getLogger("faucet.wallet")


class WalletRpcClient:
    def __init__(self) -> None:
        self._base_url = f"https://{WALLET_RPC_HOST}:{WALLET_RPC_PORT}"
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            ssl_ctx = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
            ssl_ctx.load_cert_chain(certfile=str(WALLET_CERT), keyfile=str(WALLET_KEY))
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                verify=ssl_ctx,
                timeout=30.0,
            )
        return self._client

    async def _rpc(self, endpoint: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        client = await self._ensure_client()
        resp = await client.post(endpoint, json=payload or {})
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"RPC {endpoint} failed: {data}")
        return data

    async def get_sync_status(self) -> dict[str, Any]:
        return await self._rpc("/get_sync_status")

    async def get_wallet_balance(self, wallet_id: int = 1) -> dict[str, Any]:
        data = await self._rpc("/get_wallet_balance", {"wallet_id": wallet_id})
        return data["wallet_balance"]

    async def get_next_address(self, wallet_id: int = 1, new_address: bool = False) -> str:
        data = await self._rpc("/get_next_address", {
            "wallet_id": wallet_id,
            "new_address": new_address,
        })
        return data["address"]

    async def send_transaction(
        self,
        address: str,
        amount_mojos: int,
        wallet_id: int = 1,
        fee: int = 0,
    ) -> dict[str, Any]:
        data = await self._rpc("/send_transaction", {
            "wallet_id": wallet_id,
            "address": address,
            "amount": amount_mojos,
            "fee": fee,
        })
        return data["transaction"]

    async def get_transactions(
        self,
        wallet_id: int = 1,
        start: int = 0,
        end: int = 50,
        reverse: bool = True,
    ) -> list[dict[str, Any]]:
        data = await self._rpc("/get_transactions", {
            "wallet_id": wallet_id,
            "start": start,
            "end": end,
            "reverse": reverse,
        })
        return data.get("transactions", [])

    async def get_height_info(self) -> int:
        data = await self._rpc("/get_height_info")
        return data.get("height", 0)

    async def is_available(self) -> bool:
        try:
            await self.get_sync_status()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def wait_for_ready(self, timeout: int = 120, poll_interval: int = 3) -> None:
        logger.info("Waiting for wallet RPC to become available (timeout=%ds)...", timeout)
        elapsed = 0
        while elapsed < timeout:
            if await self.is_available():
                logger.info("Wallet RPC is ready.")
                return
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        raise TimeoutError(f"Wallet RPC not available after {timeout}s")
