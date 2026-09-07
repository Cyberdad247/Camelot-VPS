const fs = require('fs');
const content = fs.readFileSync('Makefile', 'utf-8');

let newContent = content + `
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
`;

fs.writeFileSync('Makefile', newContent);
