IMAGE_NAME := chia-testnet-faucet
VERSION := $(shell cat VERSION)
REGISTRY ?=
PLATFORM ?= linux/amd64,linux/arm64

FULL_IMAGE = $(if $(REGISTRY),$(REGISTRY)/$(IMAGE_NAME),$(IMAGE_NAME))

.PHONY: build build-local save load run stop push clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

build: ## Build multi-platform image (requires buildx, pushes to registry)
	docker buildx build \
		--platform $(PLATFORM) \
		--build-arg VERSION=$(VERSION) \
		-t $(FULL_IMAGE):$(VERSION) \
		-t $(FULL_IMAGE):latest \
		--push .

build-local: ## Build image for local platform only
	docker build \
		--build-arg VERSION=$(VERSION) \
		-t $(FULL_IMAGE):$(VERSION) \
		-t $(FULL_IMAGE):latest .

save: build-local ## Export image as a tarball
	docker save $(FULL_IMAGE):$(VERSION) | gzip > $(IMAGE_NAME)-$(VERSION).tar.gz
	@echo "Saved to $(IMAGE_NAME)-$(VERSION).tar.gz"

load: ## Import image from tarball (usage: make load FILE=chia-testnet-faucet-0.1.0.tar.gz)
	docker load < $(FILE)

run: ## Start the faucet with docker compose
	docker compose up -d --build

stop: ## Stop the faucet
	docker compose down

push: build-local ## Tag and push to a registry (usage: make push REGISTRY=ghcr.io/yourname)
ifndef REGISTRY
	$(error REGISTRY is required. Usage: make push REGISTRY=ghcr.io/yourname)
endif
	docker tag $(IMAGE_NAME):$(VERSION) $(FULL_IMAGE):$(VERSION)
	docker tag $(IMAGE_NAME):$(VERSION) $(FULL_IMAGE):latest
	docker push $(FULL_IMAGE):$(VERSION)
	docker push $(FULL_IMAGE):latest

clean: ## Remove built tarballs and dangling images
	rm -f $(IMAGE_NAME)-*.tar.gz
	docker image prune -f --filter "label=org.opencontainers.image.title=$(IMAGE_NAME)"
