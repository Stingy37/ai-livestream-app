### **Template**

We log user test sessions with the following convention: 

```
[timestamp] [severity] observation
```

Severity codes:

- `OK` — smooth, no issues
- `H` — hesitation (paused 3+ seconds, scanned the page)
- `W` — wrong target (clicked something expecting different result)
- `F` — failure (could not complete without help)

Example raw notes:

```
0:00  OK  clicked "new broadcast" immediately
0:34  H   looked for "add scene" inside broadcast config, ~6s scan
0:52  OK  found scene editor via sidebar
1:28  F   couldn't find connector dot on scene graph cards, tried 3x
1:35  Q   "how do I connect these?"
2:15  H   scrolled past scheduling section twice
2:41  OK  task complete
```

---

### **Session One**

