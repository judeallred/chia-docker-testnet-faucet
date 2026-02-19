FROM ghcr.io/chia-network/chia:latest

ARG VERSION=dev

LABEL org.opencontainers.image.title="chia-testnet-faucet"
LABEL org.opencontainers.image.description="Chia testnet11 faucet with HTTP API and dashboard"
LABEL org.opencontainers.image.version="${VERSION}"

WORKDIR /faucet

COPY requirements.txt .
RUN /chia-blockchain/venv/bin/pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

ENV CHIA_MNEMONIC=""
ENV FAUCET_PORT=9090
EXPOSE 9090

ENTRYPOINT ["./entrypoint.sh"]
