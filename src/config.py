import os
from pathlib import Path

FAUCET_PORT = int(os.environ.get("FAUCET_PORT", "9090"))
SEND_AMOUNT_MOJOS = int(os.environ.get("SEND_AMOUNT_MOJOS", "1000000000"))  # 0.001 TXCH
LOW_BALANCE_MOJOS = int(os.environ.get("LOW_BALANCE_MOJOS", "10000000000"))  # 0.01 TXCH
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "3"))
RETRY_DELAY_BASE = float(os.environ.get("RETRY_DELAY_BASE", "2"))

CHIA_ROOT = Path(os.environ.get("CHIA_ROOT", "/root/.chia/mainnet"))
WALLET_RPC_PORT = int(os.environ.get("WALLET_RPC_PORT", "9256"))
WALLET_RPC_HOST = os.environ.get("WALLET_RPC_HOST", "localhost")

WALLET_CERT = CHIA_ROOT / "config" / "ssl" / "wallet" / "private_wallet.crt"
WALLET_KEY = CHIA_ROOT / "config" / "ssl" / "wallet" / "private_wallet.key"

MOJOS_PER_XCH = 1_000_000_000_000


def mojos_to_txch(mojos: int) -> str:
    return f"{mojos / MOJOS_PER_XCH:.12f}".rstrip("0").rstrip(".")
