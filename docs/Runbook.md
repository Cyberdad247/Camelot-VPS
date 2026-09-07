# Deployment & Rollback Runbook

## 1. Deployment

```bash
# SSH to VPS
ssh user@162.35.107.134

# Pull latest
cd ~/Camelot-VPS
git pull

# Rebuild
cd backend && go build ./cmd/...
cd ../crates && cargo build --release

# Restart services
sudo systemctl restart camelot-bifrost camelot-world-tree camelot-multivoice

# Verify
./deploy/health-check.sh
```

## 2. Rollback

```bash
# Revert to last known good
git checkout <last-good-commit>
go build ./cmd/...
sudo systemctl restart camelot-bifrost

# Replay receipts to last-good state
camelot-revert --receipt 0xLAST_GOOD
```
