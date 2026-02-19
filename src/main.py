"""Chia Testnet Faucet -- FastAPI application."""

import asyncio
import logging
import time
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from .config import (
    FAUCET_PORT,
    LOW_BALANCE_MOJOS,
    MAX_RETRIES,
    RETRY_DELAY_BASE,
    SEND_AMOUNT_MOJOS,
    mojos_to_txch,
)
from .wallet import WalletRpcClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("faucet")

wallet = WalletRpcClient()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

SEND_HISTORY_MAX = 200


@dataclass
class SendRecord:
    timestamp: str
    address: str
    amount_mojos: int
    status: str
    tx_id: str | None = None
    error: str | None = None


send_history: deque[SendRecord] = deque(maxlen=SEND_HISTORY_MAX)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await wallet.wait_for_ready()
    addr = await wallet.get_next_address(new_address=False)
    logger.info("Faucet vault address: %s", addr)
    yield
    await wallet.close()


app = FastAPI(title="Chia Testnet Faucet", lifespan=lifespan)


async def _get_vault_address() -> str:
    return await wallet.get_next_address(new_address=False)


async def _get_balance_mojos() -> int:
    balance = await wallet.get_wallet_balance()
    return balance.get("confirmed_wallet_balance", 0)


async def _send_with_retry(address: str) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            tx = await wallet.send_transaction(address, SEND_AMOUNT_MOJOS)
            logger.info("Send succeeded on attempt %d: tx=%s", attempt, tx.get("name"))
            return tx
        except Exception as exc:
            last_error = exc
            logger.warning("Send attempt %d/%d failed: %s", attempt, MAX_RETRIES, exc)
            if attempt < MAX_RETRIES:
                delay = RETRY_DELAY_BASE ** attempt
                logger.info("Retrying in %.1fs...", delay)
                await asyncio.sleep(delay)
    raise last_error  # type: ignore[misc]


@app.get("/send")
async def send(address: str) -> JSONResponse:
    if not address.startswith("txch1"):
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_address", "message": "Address must start with txch1"},
        )

    try:
        balance = await _get_balance_mojos()
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"error": "wallet_unavailable", "message": str(exc)},
        )

    if balance < SEND_AMOUNT_MOJOS:
        vault_address = await _get_vault_address()
        logger.warning(
            "Balance too low (%s mojos). Vault address: %s", balance, vault_address
        )
        return JSONResponse(
            status_code=503,
            content={
                "error": "insufficient_balance",
                "balance_mojos": balance,
                "balance_txch": mojos_to_txch(balance),
                "vault_address": vault_address,
                "message": "Faucet balance too low. Please send TXCH to the vault address.",
            },
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    try:
        tx = await _send_with_retry(address)
        record = SendRecord(
            timestamp=now,
            address=address,
            amount_mojos=SEND_AMOUNT_MOJOS,
            status="sent",
            tx_id=tx.get("name"),
        )
        send_history.appendleft(record)
        return JSONResponse(content={
            "status": "sent",
            "tx_id": tx.get("name"),
            "amount_mojos": SEND_AMOUNT_MOJOS,
            "amount_txch": mojos_to_txch(SEND_AMOUNT_MOJOS),
            "address": address,
        })
    except Exception as exc:
        record = SendRecord(
            timestamp=now,
            address=address,
            amount_mojos=SEND_AMOUNT_MOJOS,
            status="failed",
            error=str(exc),
        )
        send_history.appendleft(record)
        return JSONResponse(
            status_code=500,
            content={
                "error": "send_failed",
                "message": str(exc),
                "address": address,
            },
        )


@app.get("/status")
async def status() -> JSONResponse:
    try:
        balance_info = await wallet.get_wallet_balance()
        sync_info = await wallet.get_sync_status()
        height = await wallet.get_height_info()
        vault_address = await _get_vault_address()
        return JSONResponse(content={
            "vault_address": vault_address,
            "confirmed_balance_mojos": balance_info.get("confirmed_wallet_balance", 0),
            "confirmed_balance_txch": mojos_to_txch(balance_info.get("confirmed_wallet_balance", 0)),
            "pending_balance_mojos": balance_info.get("unconfirmed_wallet_balance", 0),
            "spendable_balance_mojos": balance_info.get("spendable_balance", 0),
            "synced": sync_info.get("synced", False),
            "syncing": sync_info.get("syncing", False),
            "height": height,
            "send_amount_mojos": SEND_AMOUNT_MOJOS,
            "send_amount_txch": mojos_to_txch(SEND_AMOUNT_MOJOS),
            "low_balance_threshold_mojos": LOW_BALANCE_MOJOS,
        })
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"error": "wallet_unavailable", "message": str(exc)},
        )


@app.get("/address")
async def address() -> JSONResponse:
    try:
        vault_address = await _get_vault_address()
        return JSONResponse(content={"vault_address": vault_address})
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"error": "wallet_unavailable", "message": str(exc)},
        )


@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request) -> HTMLResponse:
    try:
        balance_info = await wallet.get_wallet_balance()
        sync_info = await wallet.get_sync_status()
        height = await wallet.get_height_info()
        vault_address = await _get_vault_address()
        transactions = await wallet.get_transactions()

        confirmed = balance_info.get("confirmed_wallet_balance", 0)
        low_balance = confirmed < LOW_BALANCE_MOJOS

        tx_rows = []
        for tx in transactions[:50]:
            tx_rows.append({
                "time": datetime.fromtimestamp(
                    tx.get("created_at_time", 0), tz=timezone.utc
                ).strftime("%Y-%m-%d %H:%M:%S UTC"),
                "address": tx.get("to_address", "unknown"),
                "amount_txch": mojos_to_txch(tx.get("amount", 0)),
                "fee_txch": mojos_to_txch(tx.get("fee_amount", 0)),
                "status": "confirmed" if tx.get("confirmed") else "pending",
                "type": "outgoing" if tx.get("type", 0) == 1 else "incoming",
                "tx_id": tx.get("name", ""),
            })

        wallet_available = True
    except Exception as exc:
        logger.error("Error fetching wallet data for landing page: %s", exc)
        wallet_available = False
        confirmed = 0
        low_balance = True
        vault_address = "unavailable"
        sync_info = {}
        height = 0
        tx_rows = []

    faucet_sends = [
        {
            "time": r.timestamp,
            "address": r.address,
            "amount_txch": mojos_to_txch(r.amount_mojos),
            "status": r.status,
            "tx_id": r.tx_id or "",
            "error": r.error or "",
        }
        for r in send_history
    ]

    return templates.TemplateResponse("index.html", {
        "request": request,
        "wallet_available": wallet_available,
        "vault_address": vault_address,
        "balance_txch": mojos_to_txch(confirmed),
        "balance_mojos": confirmed,
        "low_balance": low_balance,
        "low_balance_threshold_txch": mojos_to_txch(LOW_BALANCE_MOJOS),
        "synced": sync_info.get("synced", False),
        "syncing": sync_info.get("syncing", False),
        "height": height,
        "send_amount_txch": mojos_to_txch(SEND_AMOUNT_MOJOS),
        "transactions": tx_rows,
        "faucet_sends": faucet_sends,
        "faucet_port": FAUCET_PORT,
    })
