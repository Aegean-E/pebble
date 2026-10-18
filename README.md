# pebble

## ⚡ 30-Second Cold-Start Quick Reference

- **Runtime Prerequisites**: <FILL: each runtime this project needs and its minimum version>
- **Canonical Regression Shield Gate**:
  ```bash
  python -m unittest discover
  ```

### 🛠️ AIKit Commands (run from the AIKit folder)
| Role | Command |
|---|---|
| Status, task and gates | `python aikit.py status pebble` |
| Phase 4: every gate | `python aikit.py check pebble` |
| Repair memory and map, then check | `python aikit.py fix pebble` |
| Resume an interrupted task | `python aikit.py resume pebble` |

## 📦 What's Inside

```text
pebble/
├── .gitignore                <- transient AIKit state excluded
├── README.md
└── .aikit/                   <- this project's memory: record, ledger, decisions
```
