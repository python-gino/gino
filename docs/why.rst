=====================
Why Asynchronous ORM?
=====================

Normally the answer is no, you don't need an asynchronous ORM. Before moving
on, you should read `this blog post <http://techspot.zzzeek.org/2015/02/15/asynchronous-python-and-databases/>`_
from Mike Bayer, the author of SQLAlchemy. Though it was written before the
project uvloop, but his points are still valid now:

1. Async is usually not essential for stereotypical database logic;
2. Async is **slower**, not faster, measured in single-routine.

So a general suggestion would be, don't use it. When you really need it, you
will know why it is required. Even then, caution must be taken because
asynchronous ORM is a minefield biting noses.

**THIS IS A WIP**
