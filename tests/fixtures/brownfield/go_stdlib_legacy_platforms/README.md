# Legacy Go platform fixture

This dependency-free legacy application exposes the same quote-order behavior
through two exact non-HTTP boundaries:

- a command process with strict arguments, canonical stdout, and exit status;
- a temporally decoupled file-spool event flow whose enqueue, dispatch, and
  observation stages run as separate processes.

Runtime spool data belongs outside this source tree. UCF inventory, adapter
builds, and verification must leave these nine regular source files unchanged.
The fixture is not a general shell, queue, broker, delivery, durability,
ordering, or exactly-once implementation.
