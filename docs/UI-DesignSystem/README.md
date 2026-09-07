# UI Design System: Camelot-VPS HUD

## 1. Color Palette

| Token | Value | Usage |
|-------|-------|-------|
| `--obsidian` | `#0d0c15` | Background |
| `--royal-purple` | `#6b4c9a` | Cards |
| `--luxora-gold` | `#f5c542` | Primary actions |
| `--cyan` | `#00e5ff` | Running state |
| `--amber` | `#ffbf00` | Approval required |
| `--red` | `#ff4444` | Failed/quarantined |
| `--violet` | `#9d4edd` | Stale |
| `--gray` | `#888888` | Inactive |

## 2. Components

- **Navbar:** Logo, user menu, vitals summary.
- **Sidebar:** Navigation (Dashboard, Missions, Approvals, Receipts, Settings).
- **Vitals Panel:** RAM, CPU, latency, error rate (5s refresh).
- **Mission Canvas:** Mission list, detail view, task graph.
- **Approval Drawer:** Pending approvals with manifest evidence.
- **Receipt Timeline:** Hash-chained receipt stream (3s refresh).
- **World Tree Canvas:** WebGPU graph topology (nodes, edges, halos).

## 3. Accessibility

- All canvas data mirrored in DOM fallback.
- Semantic HTML, ARIA labels, keyboard navigation.
