=====================
Why Asynchronous ORM?
=====================

Normally the answer is no, you don't need an asynchronous ORM. Before moving
on, you should read `this blog post
<http://techspot.zzzeek.org/2015/02/15/asynchronous-python-and-databases/>`_
from Mike Bayer, the author of SQLAlchemy. Though it was written before the
project `uvloop <https://github.com/MagicStack/uvloop>`_, but his points are
still valid now:

1. Async is usually not essential for stereotypical database logic;
2. Async is **slower**, not faster, measured in single-routine.

Next, we'll roughly go through what is asynchronous I/O again, and its
pros/cons in practice, as well as why asynchronous ORM can be helpful.


The Story
---------

Let's say we want to build a search engine. We'll use a single core computer to
build our index. To make things simpler, our tasks are to fetch web pages, and
process their content. Each task looks like this:

.. image:: why_single_task.png

We have lots of web pages to index, so we simply handle them one by one:

.. image:: why_throughput.png

We assume the time of each task is constant. Within 1 second, 2 tasks are done.
So we can say, the throughput of current system is 2 tasks/sec. How can we
improve the throughput? An obvious answer is to add more CPU cores:

.. image:: why_multicore.png

This simply doubles our throughput to 4 tasks/sec, and linearly scales as we
adding more CPU cores, if the network is not a bottleneck. But can we improve
the throughput for each CPU core? The answer is yes, we can use
multi-threading:

.. image:: why_multithreading.png

Wait a second here, 2 threads barely finished 6 tasks in 2 seconds, the
throughput is only 2.7 tasks/sec, much lower than 4 tasks/sec with 2 cores.
What's wrong with multi-threading? From the diagram we can see:

* There are yellow bars taking up extra time.
* The green bars can still overlap with any bar in the other thread, but
* non-green bars cannot overlap with non-green bars in the other thread.

The yellow bars are time taken by `context switches
<https://en.wikipedia.org/wiki/Context_switch>`_, a technique to allow multiple
threads or processes to run on a single CPU core concurrently. Because one CPU
core can do only one thing at a time (let's assume a world without
`Hyper-threading <https://en.wikipedia.org/wiki/Hyper-threading>`_ or something
like that), so in order to run several threads concurrently, the CPU must
`split its time <https://en.wikipedia.org/wiki/Time-sharing>`_ into small
slices, and run a little bit of each thread with these slices. The yellow bar
is the very cost for CPU to switch its context to run a different thread. The
scale is a bit dramatic, but it makes the point.

Wait again here, the green bars are overlapping between threads, the CPU is
doing two things at the same time? No, the CPU is doing nothing in the middle
of the green bar, because it's waiting for the HTTP response (I/O). That's why
multi-threading could improve the throughput to 2.7, instead of making it
worse to 1.7 tasks/sec. You may try in real to run CPU-intensive tasks with
multi-threading on single core, there won't be any improvement. Like the
multiplexed red bars (in practice there might be more context switches
depending on the task), they seems to be running at the same time, but the
total time for all to finish is actually longer than running each of them one
by one. That's also why this is called concurrency instead of parallelism.

Foreseeably as adding more threads, the increase of throughput will slow down,
or even get decreasing, because context switches are wasting too much time,
not to mention the extra memory footprint taken by new threads. It is usually
not quite practical to have tens of thousands of threads running on a single
CPU core. But is it possible to have tens of thousands of I/O-bound tasks to
run concurrently on a single CPU core somehow? This is the once-famous `C10k
problem <https://en.wikipedia.org/wiki/C10k_problem>`_, usually solved by
asynchronous I/O:

.. image:: why_coroutine.png

.. note::

    Asynchronous I/O and coroutine are two different things, but they usually
    work together.

Awesome! The throughput is 3.7 tasks/sec, almost as good as 4 tasks/sec of 2
CPU cores. Yes this is not real data, it is quite unfair for multi-threading:

* Asynchronous I/O has context switches too, it's just faster than OS context
  switches. I shouldn't omit the yellow bars just because they are small. (Yet
  I did because they are too small)
* There is also extra framework code for asynchronous I/O taking time.
* Coroutines have memory footprints too.

But comparingly, asynchronous I/O is still a better fit for the C10k problem,
especially the whole thing is managable in application code.

So why asynchronous I/O?

* To efficiently use CPU and memory with lots of concurrent I/O-bound tasks.
* Thus to improve throughput with limited hardware, not to make each task
  run any faster - it is actually slower.


**THIS IS A WIP**
