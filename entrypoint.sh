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

SAVED_MNEMONIC="/root/.chia/faucet_mnemonic.txt"

KEY_COUNT=$(chia keys show 2>/dev/null | grep -c "Fingerprint:" || true)
if [ "$KEY_COUNT" -gt 0 ]; then
    echo "Found $KEY_COUNT existing key(s)."
elif [ -n "${CHIA_MNEMONIC:-}" ]; then
    echo "Importing key from CHIA_MNEMONIC environment variable..."
    TMPFILE=$(mktemp)
    echo "$CHIA_MNEMONIC" > "$TMPFILE"
    chia keys add -f "$TMPFILE"
    rm -f "$TMPFILE"
    echo "Key imported successfully."
elif [ -f "$SAVED_MNEMONIC" ]; then
    echo "Re-importing key from saved mnemonic file..."
    chia keys add -f "$SAVED_MNEMONIC"
    echo "Key re-imported successfully."
else
    echo "============================================"
    echo "  No keys found. Generating a new key..."
    echo "============================================"
    chia keys generate | tee /tmp/chia_key_output.txt
    grep -A1 "mnemonic" /tmp/chia_key_output.txt | tail -1 | xargs > "$SAVED_MNEMONIC"
    chmod 600 "$SAVED_MNEMONIC"
    rm -f /tmp/chia_key_output.txt
    echo ""
    echo "============================================"
    echo "  BACK UP THE MNEMONIC ABOVE!"
    echo "  Mnemonic also saved to $SAVED_MNEMONIC"
    echo "  in the persistent chia_data volume."
    echo "============================================"
    echo ""
fi

echo "Starting chia wallet service..."
chia start wallet

echo "Wallet service started. Launching faucet API..."
exec /chia-blockchain/venv/bin/python -m uvicorn src.main:app \
    --host 0.0.0.0 \
    --port "${FAUCET_PORT:-9090}" \
    --log-level info
