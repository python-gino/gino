---
name: Bug report
about: Create a report to help us improve
title: ''
labels: bug
assignees: ''

---

**Describe the bug**
A clear and concise description of what the bug is.

**To Reproduce**
Please provide a self-contained script to reproduce the bug if possible.
```python
from gino import Gino

db = Gino()

async def main():
    async with db.with_bind("postgresql:///"):
        ...
```

**Expected result**
```
The expected output or behavior of the script (when the bug is fixed).
```

**Actual result**
```
The actual output or behavior of the script (before a bugfix).
```

**Environment (please complete the following information):**
 - GINO: [e.g. 1.0.1]
 - SQLAlchemy: [e.g. 1.3.10]
 - Other: [e.g. Linux, macOS, PostgreSQL 9.6, asyncpg 0.18, aiomysql 0.0.20]

**Additional context**
Add any other context about the problem here.
