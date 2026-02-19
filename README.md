# Chia Testnet Faucet

A self-contained, Dockerized faucet for Chia testnet11. Dispenses TXCH via a simple HTTP GET to seed local e2e tests and other development workflows.

## Purpose

This faucet exists to make local development easier. When you're running integration tests, e2e suites, or experimenting with Chia tooling, you often need a quick way to fund throwaway wallets with testnet coins. This service sits on your local network, accepts a GET request with a target address, and sends TXCH -- no friction, no waiting.

**This is deliberately insecure.** There is no captcha, no rate limiting, no authentication, and no abuse prevention of any kind. It is intended exclusively for personal, testnet-only use. Do not expose it to the public internet.

**Always use throwaway private keys.** The faucet is designed for convenience, not robustness. The mnemonic is stored in plaintext in a Docker volume and may appear in container logs. Treat the faucet wallet as disposable -- fund it with small amounts of TXCH and don't reuse its key for anything else.

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

## Distribution

### Build locally

```bash
make build-local
```

This produces `chia-testnet-faucet:latest` and `chia-testnet-faucet:0.1.0` on your local Docker.

### Export as a tarball

```bash
make save
```

Produces `chia-testnet-faucet-0.1.0.tar.gz`. Share this file -- the recipient loads it with:

```bash
make load FILE=chia-testnet-faucet-0.1.0.tar.gz
# or: docker load < chia-testnet-faucet-0.1.0.tar.gz
```

### Push to a registry

```bash
make push REGISTRY=ghcr.io/yourname
```

This tags and pushes `ghcr.io/yourname/chia-testnet-faucet:0.1.0` and `:latest`. You need to `docker login` to the registry first.

### Multi-platform build

```bash
make build REGISTRY=ghcr.io/yourname
```

Builds for `linux/amd64` and `linux/arm64` and pushes directly to the registry (multi-platform builds require a registry or `--load` with a single platform).

### All make targets

```bash
make help
```

## Using the Faucet from Another Project

### Option 1: Add to your project's docker-compose

Copy `docker-compose.standalone.yml` into your project, or reference the image directly. If the image was built locally or loaded from a tarball:

```yaml
services:
  your-app:
    build: .
    # ...

  faucet:
    image: chia-testnet-faucet:latest
    ports:
      - "9090:9090"
    volumes:
      - faucet_data:/root/.chia
      - faucet_keys:/root/.chia_keys
    environment:
      - CHIA_MNEMONIC=${FAUCET_MNEMONIC:-}

volumes:
  faucet_data:
  faucet_keys:
```

If published to a registry, replace the image line:

```yaml
    image: ghcr.io/yourname/chia-testnet-faucet:latest
```

Then from your app or tests, the faucet is at `http://faucet:9090` (container-to-container) or `http://localhost:9090` (from the host).

### Option 2: Run standalone, call from anywhere

Leave the faucet running as a background service:

```bash
cd /path/to/faucet
docker compose up -d
```

From any project on the same machine, just make HTTP calls:

```bash
curl "http://localhost:9090/send?address=txch1..."
```

Or in your test code:

```python
import requests

def fund_wallet(address: str) -> dict:
    resp = requests.get(f"http://localhost:9090/send?address={address}")
    resp.raise_for_status()
    return resp.json()
```

## Architecture

The container runs two processes:
1. **Chia lite wallet** -- connects to testnet11 peers, syncs blockchain headers, manages wallet state
2. **FastAPI server** -- communicates with the wallet via its local RPC API (HTTPS + mTLS on localhost:9256)
