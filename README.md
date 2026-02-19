# Chia Testnet Faucet

A self-contained, Dockerized faucet service for Chia testnet11. Runs a lite wallet, manages its own keys, and dispenses 0.001 TXCH per request via a simple HTTP GET.

## Quick Start

```bash
docker compose up -d --build
```

The faucet will:
1. Initialize Chia and configure for testnet11
2. Generate a key pair on first run (check logs for the mnemonic backup)
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

## First-Run Setup

On first launch, check the container logs for the generated mnemonic:

```bash
docker compose logs faucet
```

Look for the `BACK UP THE MNEMONIC ABOVE!` banner. Save this mnemonic securely -- it's the only way to recover the faucet's wallet.

The faucet address will be printed in the logs and is also available at `/address` or on the dashboard. Send TXCH to this address to fund the faucet.

You can get testnet TXCH from:
- https://testnet11-faucet.chia.net/
- https://txchfaucet.com/

## Configuration

All settings are configurable via environment variables (set in `docker-compose.yml` or a `.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
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

Docker volumes `chia_data` and `chia_keys` persist the wallet database, blockchain state, and keyring across container restarts. Your keys and wallet state survive `docker compose down` and `docker compose up`.

To fully reset (destroys keys and wallet):
```bash
docker compose down -v
```

## Architecture

The container runs two processes:
1. **Chia lite wallet** -- connects to testnet11 peers, syncs blockchain headers, manages wallet state
2. **FastAPI server** -- communicates with the wallet via its local RPC API (HTTPS + mTLS on localhost:9256)
