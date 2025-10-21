import asyncio

from py_tmi.event_emitter import EventEmitter


def test_event_emitter_handles_async_listeners():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    emitter = EventEmitter()
    called = asyncio.Event()

    async def listener(value):
        await asyncio.sleep(0.01)
        if value == 42:
            called.set()

    emitter.on("test", listener)

    async def runner():
        emitter.emit("test", 42)
        await asyncio.wait_for(called.wait(), timeout=0.5)

    loop.run_until_complete(runner())
    loop.close()
    asyncio.set_event_loop(None)


def test_emit_many_dispatches_payloads():
    emitter = EventEmitter()
    results = []

    emitter.on("first", lambda *args: results.append(("first", args)))
    emitter.on("second", lambda *args: results.append(("second", args)))

    emitter.emit_many(["first", "second"], [(1,), (2,)])

    assert results == [("first", (1,)), ("second", (2,))]
