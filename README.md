# Chia Testnet Faucet

A self-contained, Dockerized faucet service for Chia testnet11. Runs a lite wallet, manages its own keys, and dispenses 0.001 TXCH per request via a simple HTTP GET.

## Quick Start

```bash
docker compose up -d --build
```

The faucet will:
1. Initialize Chia and configure for testnet11
2. Import or generate a wallet key (see Key Management below)
3. Start a lite wallet and begin syncing
4. Launch the API on port 9090

## Usage

**Send TXCH:**
```bash
curl http://localhost:9090/send?address=txch1...
```

**Check status:**
```bash
curl http://localhost:9090/status
```

**Get the faucet address (to fund the faucet):**
```bash
curl http://localhost:9090/address
```

**Dashboard:** Open http://localhost:9090 in a browser to see balance, faucet address, and transaction history.

## Key Management

The faucet needs a Chia wallet key. There are two ways to provide one:

### Option 1: Bring your own key

Set the `CHIA_MNEMONIC` environment variable to your 24-word mnemonic phrase before first launch:

```bash
CHIA_MNEMONIC="word1 word2 word3 ... word24" docker compose up -d --build
```

Or add it to a `.env` file alongside `docker-compose.yml`:

```
CHIA_MNEMONIC=word1 word2 word3 ... word24
```

The mnemonic is imported on first boot. It is written to a temp file for import and then deleted -- it does not persist in the container filesystem. However, it is visible via `docker inspect` and the process environment. For testnet use this is fine.

### Option 2: Auto-generate

Leave `CHIA_MNEMONIC` unset and the faucet will generate a new key on first boot:

```bash
docker compose up -d --build
docker compose logs faucet   # look for the mnemonic
```

The generated mnemonic is:
- Printed to the container logs (one-time, for backup)
- Saved to `/root/.chia/faucet_mnemonic.txt` inside the persistent `chia_data` volume

### Key persistence

Keys are persisted across container restarts through three layers (checked in order on each boot):

1. **Keyring** (`chia_keys` volume) -- primary storage, survives normal down/up cycles
2. **Saved mnemonic file** (`chia_data` volume) -- auto-created on key generation; allows recovery if the keyring volume is lost
3. **`CHIA_MNEMONIC` env var** -- used on first boot to seed the keyring

Only `docker compose down -v` (which destroys both volumes) loses the key. In that case, re-provide `CHIA_MNEMONIC` or a new key will be generated.

### Funding the faucet

The faucet address is available at `/address`, on the dashboard, and in the startup logs. Send TXCH to this address to fund the faucet.

You can get testnet TXCH from:
- https://testnet11-faucet.chia.net/
- https://txchfaucet.com/

## Configuration

All settings are configurable via environment variables (set in `docker-compose.yml` or a `.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `CHIA_MNEMONIC` | *(empty)* | 24-word mnemonic to import on first boot |
| `FAUCET_PORT` | `9090` | Port the API listens on |
| `SEND_AMOUNT_MOJOS` | `1000000000` | Amount per send (0.001 TXCH) |
| `LOW_BALANCE_MOJOS` | `10000000000` | Low balance threshold (0.01 TXCH) |
| `MAX_RETRIES` | `3` | Retry attempts on send failure |
| `RETRY_DELAY_BASE` | `2` | Base delay for exponential backoff (seconds) |

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | HTML dashboard with balance, faucet address, transaction history |
| `/send?address=txch1...` | GET | Send 0.001 TXCH to the address |
| `/status` | GET | JSON wallet status (balance, sync, height) |
| `/address` | GET | JSON faucet address |

### Error Responses

- **400** -- Invalid address (must start with `txch1`)
- **500** -- Send failed after all retries
- **503** -- Wallet unavailable or balance too low (response includes faucet address for funding)

## Persistence

Docker volumes `chia_data` and `chia_keys` persist the wallet database, blockchain state, keyring, and saved mnemonic across container restarts. Your keys and wallet state survive `docker compose down` and `docker compose up`.

To fully reset (destroys keys, wallet, and saved mnemonic):
```bash
docker compose down -v
```

## Architecture

The container runs two processes:
1. **Chia lite wallet** -- connects to testnet11 peers, syncs blockchain headers, manages wallet state
2. **FastAPI server** -- communicates with the wallet via its local RPC API (HTTPS + mTLS on localhost:9256)
