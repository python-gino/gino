Why Asynchronous ORM?
=====================

Conclusion first: in many cases, you don't need to use an asynchronous ORM, or even
asyncio itself. But when you do, it's very important to get it done correctly.


When asyncio Helps
------------------

As Mike Bayer - the author of SQLAlchemy - `pointed out
<http://techspot.zzzeek.org/2015/02/15/asynchronous-python-and-databases/>`__, even
Python itself can be slower than the database operation in a stereotypical
business-style CRUD-ish application, because the modern databases are so fast when the
query is simple, and this kind of application usually deploys the database in a super
reliable network. In this case, it doesn't make sense to say "Hey I wanna use asyncio
because I love this asynchronous ORM".

The problem asyncio solves is quite different: when you need to deal with a lot of
concurrent tasks, some of which may block on I/O for arbitrary time, asyncio could
largely leverage the scalability with cooperative multitasking. This is explained in
:doc:`async`. So the ultimate reason to use asyncio should be the application itself,
not the database.

For example, a chat server may need to talk to tens of thousands of clients at the same
time. The clients are idle for most of the time, because the user didn't send a message
in seconds, which is thousands of times longer than the time needed by the server to
handle the message. Obviously the last thing you want is to have tens of thousands of OS
threads to wait for each of those clients to reply, as it'll disproportionately consume
way too much hardware resource. In contrast, asyncio could easily handle this
concurrency with reasonably tiny overhead.

.. image:: ../images/263px-Minimum-Tonne.svg.png
   :align: right

Another example is authentication using `OpenID Connect Authorization Code Flow
<https://openid.net/specs/openid-connect-core-1_0.html#CodeFlowAuth>`__ as a Client. If
the Token Endpoint of the Authorization Server responds fast, everything is fine. But
once it's delayed for even just a few seconds due to unreliable Internet or overloaded
server or whatever reasons, the Client would face a concurrency challenge. According to
`Liebig's law <https://en.wikipedia.org/wiki/Liebig%27s_law_of_the_minimum>`__, the
minimum throughput of the Client or the Server determines the overall performance.
Comparing to asyncio, it's not wise to use threading model to build the Client and rely
on the Internet which may make the Client the shortest stave.

Arbitrary delays may happen in the database too. In PostgreSQL, you can |LISTEN|_ to
some asynchronous events that happens unpredictably. Some normal bulk queries may also
take a long time to run, and the database locks can occasionally block too, especially
the dead ones. But these are usually not considered as a high-concurrency scenario,
because the database will possibly hit its bottleneck before your server does, or there
are smarter ways to handle such situations than asyncio. Nevertheless, the database
could be the reason to use asyncio, depending on the actual case.

In closing, there are scenarios when asyncio could help with concurrency issues. Now
that we know we will write an asynchronous server, then the next question is:

.. |LISTEN| replace:: ``LISTEN``
.. _LISTEN: https://www.postgresql.org/docs/current/sql-listen.html


How to Access Database
----------------------

The first thing to balance here is ORM - how much convenience would you like to
sacrifice for execution performance. As we are talking about ORM, let's assume we need
at least some level of abstraction over raw SQL, or else low-level tools like asyncpg
would be a neat choice. Don't get me wrong - asyncpg is great and convenient to use, but
there won't be such a question "why asynchronous ORM" if we're not seeking an objective
layer over bare SQL. It's totally reasonable and sometimes beneficial and fun to play
with SQL in asynchronous contexts, it's just out of our scope here.

Because simple queries are executed so fast in the database, one obvious but wrong
approach is to just run the query in the main thread. It won't work because it will 100%
cause a dead lock - not a typical database dead lock, but a hybrid one between the
connection pool and cooperative multitasking. For example, here's a very simple server::

    import asyncio
    from fastapi import FastAPI
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    app = FastAPI()
    e = create_engine("postgresql://localhost")
    Session = sessionmaker(bind=e)


    @app.get("/")
    async def read_root():
        session = Session()
        try:
            now = session.execute("SELECT now()").scalar()
            await asyncio.sleep(0.1)  # do some async work
            return str(now)
        finally:
            session.close()

This follows advices found in :ref:`session_faq_whentocreate` from SQLAlchemy - linking
the **session scope** to the request scope. It works fine within 10 concurrent requests,
but freezes miserably for any number beyond 10: all requests hang and the only way to
stop the server is ``kill -9``.

What just happened is called a `resource starvation
<https://en.wikipedia.org/wiki/Starvation_(computer_science)>`__. While the first 10
requests were waiting for the async work (``sleep(0.1)``), the 11th request came in and
tried to acquire a new database connection from the pool. But the connection pool is
already exhausted (default ``max_overflow=10``) by the first 10 requests, the 11th
request was then blocked by the acquisition. However, this acquisition is unfortunately
a blocking operation, therefore the main thread is blocked and the first 10 requests
lost their chance to finish the async work and return their connection back to the pool
to resume the 11th's acquisition.

The root cause of such starvation is making asynchronous calls in a **transaction
scope** created implicitly by the default ``autocommit=False``. So other than limiting
the number of concurrent requests down to 10, a more reasonable solution is to avoid
doing asynchronous calls in **transaction scopes** by explicitly ending them::

    @app.get("/")
    async def read_root():
        session = Session()
        try:
            now = session.execute("SELECT now()").scalar()
            session.rollback()  # return the connection to avoid starvation
            await asyncio.sleep(0.1)  # do some async work
            return str(now)
        finally:
            session.close()

Because of the implicit nature of typical ORMs, it's very hard to identify all such
**transaction scopes** and make sure there's no ``await`` in them - you may have started
an implicit transaction by simply accessing a property like ``current_user.name``. In
practice, it is an impossible mission to correctly mix blocking ORM code with
asynchronous programming in the same thread. So never do this.

What about thread pool?

The idea is to defer all blocking code into a thread pool, and run asynchronous
cooperative multitasking in the main thread. This is theoretically possible, but the
same implicit ORM issue keeps haunting us - how do you guarantee there is no blocking
calls in the main thread? Taking one step back, let's assume we could do this cleanly.
What would the code look like? There must be a clear API as the logical separation
between the blocking and asynchronous code -  the server executes major DB-free business
logic in the main thread with asynchronous programming, and calls blocking methods for
encapsulated database operations in a thread pool.

This reminds me of its opposite pattern, where the main server runs in blocking mode,
deferring I/O intensive operations into a task queue like Celery_. Both approaches solve
the problem, the reason to choose one over the other is on the concentration of business
logic - you'd want to write the majority of your code in the main server, and defer only
sub-tasks or low priority operations into a thread pool or task queue. In reality, using
a task queue to e.g. send emails is a more reasonable approach. If you're doing that in
the opposite way, you may want to reconsider the design.

In summary, other than using raw SQL, the existing typical ORMs could not serve
asynchronous programming well enough. We need true asynchronous ORMs.

.. _Celery: http://www.celeryproject.org/


Asynchronous ORM Done Right
---------------------------

I would describe a proper asynchronous ORM as follows:


Don't Starve.
^^^^^^^^^^^^^

The very basic requirement for an asynchronous ORM is to avoid resource starvation, at
least avoid the part caused by the ORM design. The fix is actually pretty
straightforward - just make everything ``async``.

In the example above, if the connection acquisition is asynchronous, it won't block the
main thread any more (it'll block it's own coroutine instead). Therefore, the other
tasks would get a chance to finish the async work and return the connection back to the
pool, thus the starvation is avoided::

    @app.get("/")
    async def read_root():
        async with db.acquire() as conn:  # }
            async with conn.begin():      # } These two won't block the main thread
                now = await db.scalar("SELECT now()")
                await asyncio.sleep(0.1)  # do some async work
                return str(now)

Even though this code won't cause any resource starvation, using ``await`` within
database transactions is still strongly discouraged, unless it is for the database query
or absolutely necessary. Because after yielding the execution, we have no idea when we
can resume the following execution. That leads to a hanging transaction or at least an
unused database connection for a moment. Doing so won't kill the server immediately, but
it has a few disadvantages:

1. As the database connection pool is usually much smaller than the asynchronous server
   concurrency, this kind of code caps the concurrency down to the DB pool level.
2. Taking a database connection from the pool for nothing is a waste of resource,
   especially when the database pool is the shortest stave.
3. Database transactions should be kept short as much as possible. Because long-hanging
   transactions may keep certain database locks, leading to performance issues or even
   triggering a chain reaction of deadlocks.


Be explicit.
^^^^^^^^^^^^

With that said, it is especially important to make everything explicit - all the
connection acquisition, transactions and executions. Anything that will block must be
marked with an ``await`` or ``async with``, so that you'll know for sure when a
statement is trying to make any database I/O. Fortunately there's no other way in
asyncio to do this - following `the pattern of Twisted
<https://glyph.twistedmatrix.com/2014/02/unyielding.html>`__, asyncio is already forcing
explicit ``await`` for any asynchronous operations.

Being explicit in other part of the ORM design is also useful for enhancing the quality
of users' code. This has nothing to do with asynchronous, it's not a golden standard or
something with a clear cut either. For example:

* We could design the ORM model instances to be stateless, so that the users don't have
  to learn and worry about maintaining the state of the instances.
* There shouldn't be any "buffered operations" which users could "flush" with a single
  statement once for all.
* The user should just give direct one-off commands and the ORM executes them right away.
* Also I think the convenience tooling should be well-balanced, the user doesn't have to
  guess or remember what an API means - for example, there're more than one ways to load
  a many-to-one relationship, I'd prefer to write the query by myself rather than trying
  to remember what "join_without_n_plus_1()" means.


Be productive.
^^^^^^^^^^^^^^

Explicitness and productivity are kind of like two sides of the same coin - more
explicitness means less productive, and more convenience means less explicit. As we are
already using Python, being able to code productively is especially important. For an
asynchronous ORM, is it possible to find a proper balance between the two?

I think some of the fundamental principals must be explicit, for example the stateless
model and asynchronous yieldings. Then we could add convenient tooling on top of this
foundation as much as it doesn't harm the basic explicitness. The tooling could better
be simple wrappers, grammar sugars or shortcuts for lengthy code, with a proper and
intuitive naming. This is mostly the idea behind GINO's design.

Additionally, being able to leverage an existing ecosystem is also an important part in
productivity. People could use what they've learned directly, port what they wrote to
the new platform with minimum effort. More importantly - reuse some of the tools from
the ecosystem without having to reinvent the wheel again.
