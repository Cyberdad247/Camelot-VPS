.PHONY: build-all install clean check-hub build-bifrost build-operator build-receipts build-sentinel build-vfs build-scheduler build-worldtree

PREFIX ?= /opt/camelot
BIN_DIR = $(PREFIX)/bin

build-all: build-bifrost build-operator build-receipts build-sentinel build-vfs build-scheduler build-worldtree

build-bifrost:
	@echo "=> Building Bifrost (Go)..."
	mkdir -p bin
	cd apps/bifrost-hub && go build -ldflags="-s -w" -o ../../bin/bifrost .

check-hub:
	@echo "=> Checking native Bifrost formatting..."
	@test -z "$$(cd apps/bifrost-hub && gofmt -l .)" || (echo "Bifrost Go files require gofmt" && cd apps/bifrost-hub && gofmt -d . && exit 1)
	@echo "=> Running Bifrost unit tests..."
	cd apps/bifrost-hub && go test ./...
	@echo "=> Running Bifrost vet..."
	cd apps/bifrost-hub && go vet ./...
	@echo "=> Validating Hub JSON contracts and crystal..."
	jq empty contracts/bifrost-envelope.schema.json contracts/workspace-event.schema.json crystal/vps-hub-integration-crystal.json
	@echo "=> VPS Hub contract gate passed."

build-operator:
	@echo "=> Building Operator Console (Go)..."
	cd apps/operator-console && go build -ldflags="-s -w" -o ../../bin/operator-console main.go

build-scheduler:
	@echo "=> Building Task Scheduler (Go)..."
	cd apps/task-scheduler && go build -ldflags="-s -w" -o ../../bin/task-scheduler main.go

build-worldtree:
	@echo "=> Building World Tree API (Go)..."
	cd apps/world-tree-api && go build -ldflags="-s -w" -o ../../bin/world-tree-api main.go

build-receipts:
	@echo "=> Building Receipt Service (Rust)..."
	cargo build --release --manifest-path apps/receipt-service/Cargo.toml
	mkdir -p bin
	cp target/release/receipt-service bin/

build-sentinel:
	@echo "=> Building Sentinel Policy Engine (Rust)..."
	cargo build --release --manifest-path apps/sentinel/Cargo.toml
	mkdir -p bin
	cp target/release/sentinel bin/

build-vfs:
	@echo "=> Building VFS Guardian (Rust)..."
	cargo build --release --manifest-path apps/vfs-guardian/Cargo.toml
	mkdir -p bin
	cp target/release/vfs-guardian bin/

install: build-all
	@echo "=> Installing binaries to $(BIN_DIR)"
	mkdir -p $(BIN_DIR)
	cp bin/bifrost $(BIN_DIR)/
	cp bin/operator-console $(BIN_DIR)/
	cp bin/receipt-service $(BIN_DIR)/
	cp bin/sentinel $(BIN_DIR)/
	cp bin/vfs-guardian $(BIN_DIR)/
	cp bin/task-scheduler $(BIN_DIR)/
	cp bin/world-tree-api $(BIN_DIR)/
	@echo "=> Installing Static Assets..."
	mkdir -p /opt/camelot/static
	cp -r apps/operator-console/static/* /opt/camelot/static/ || true
	@echo "=> Installing Systemd units..."
	cp infra/systemd/*.slice /etc/systemd/system/
	cp infra/systemd/*.service /etc/systemd/system/
	systemctl daemon-reload

clean:
	rm -rf bin/
	cargo clean
build-gideon:
	@echo "=> Building Gideon (Rust)..."
	cargo build --release --manifest-path apps/gideon/Cargo.toml
	mkdir -p bin
	cp target/release/gideon bin/

build-node-agent:
	@echo "=> Building Node Agent (Rust)..."
	cargo build --release --manifest-path apps/node-agent/Cargo.toml
	mkdir -p bin
	cp target/release/node-agent bin/

build-hermes:
	@echo "=> Building Hermes Adapter (Go)..."
	cd adapters/hermes-adapter && go mod init camelot.vps/hermes || true
	cd adapters/hermes-adapter && go build -ldflags="-s -w" -o ../../bin/hermes-adapter main.go

install-phase3: build-gideon build-node-agent build-hermes
	cp bin/gideon $(BIN_DIR)/
	cp bin/node-agent $(BIN_DIR)/
	cp bin/hermes-adapter $(BIN_DIR)/
	cp infra/systemd/*.service /etc/systemd/system/
	systemctl daemon-reload

build-bitnet:
	@echo "=> Setting up BitNet Python Environment..."
	mkdir -p venv
	python3 -m venv venv || true
	./venv/bin/pip install -r apps/bitnet-worker/requirements.txt || true
	mkdir -p bin
	cp apps/bitnet-worker/worker.py bin/

install-phase4: build-bitnet
	@echo "=> Installing Phase 4 (BitNet Worker)..."
	cp infra/systemd/bitnet-worker.service /etc/systemd/system/
	systemctl daemon-reload
