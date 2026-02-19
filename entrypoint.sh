#!/usr/bin/env bash
set -euo pipefail

CHIA_ROOT="${CHIA_ROOT:-/root/.chia/mainnet}"

echo "=== Chia Testnet Faucet - Entrypoint ==="

if [ ! -d "$CHIA_ROOT" ]; then
    echo "First run: initializing chia..."
    chia init
fi

echo "Configuring for testnet..."
chia configure --testnet true

KEY_COUNT=$(chia keys show 2>/dev/null | grep -c "Fingerprint:" || true)
if [ "$KEY_COUNT" -eq 0 ]; then
    echo "============================================"
    echo "  No keys found. Generating a new key..."
    echo "============================================"
    chia keys generate | tee /tmp/chia_key_output.txt
    echo ""
    echo "============================================"
    echo "  BACK UP THE MNEMONIC ABOVE!"
    echo "  It will not be shown again."
    echo "============================================"
    echo ""
else
    echo "Found $KEY_COUNT existing key(s)."
fi

echo "Starting chia wallet service..."
chia start wallet

echo "Wallet service started. Launching faucet API..."
exec /chia-blockchain/venv/bin/python -m uvicorn src.main:app \
    --host 0.0.0.0 \
    --port "${FAUCET_PORT:-9090}" \
    --log-level info
