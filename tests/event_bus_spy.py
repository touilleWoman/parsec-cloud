import trio
import attr
import pendulum
from contextlib import contextmanager
from unittest.mock import ANY

from parsec.event_bus import EventBus


@attr.s(frozen=True, slots=True)
class SpiedEvent:
    event = attr.ib()
    kwargs = attr.ib(factory=dict)
    dt = attr.ib(factory=pendulum.now)


@attr.s(repr=False)
class EventBusSpy:
    ANY = ANY  # Easier to use than doing an import
    events = attr.ib(factory=list)
    _waiters = attr.ib(factory=set)

    def __repr__(self):
        return f"<{type(self).__name__}({[e.event for e in self.events]})>"

    def _on_event_cb(self, event, **kwargs):
        cooked_event = SpiedEvent(event, kwargs)
        self.events.append(cooked_event)
        for waiter in self._waiters.copy():
            waiter(cooked_event)

    def clear(self):
        self.events.clear()

    async def wait_for_backend_connection_ready(self):
        for occured_event in reversed(self.events):
            if occured_event.event == "backend.connection.ready":
                return occured_event
            elif occured_event.event == "backend.connection.lost":
                break

        return await self._wait(SpiedEvent("backend.connection.ready", dt=ANY))

    async def wait(self, event, dt=ANY, kwargs=ANY):
        expected = SpiedEvent(event, kwargs, dt)
        for occured_event in reversed(self.events):
            if expected == occured_event:
                return occured_event

        return await self._wait(expected)

    async def _wait(self, cooked_expected_event):
        catcher = trio.Queue(1)

        def _waiter(cooked_event):
            if cooked_expected_event == cooked_event:
                catcher.put_nowait(cooked_event)
                self._waiters.remove(_waiter)

        self._waiters.add(_waiter)
        return await catcher.get()

    async def wait_multiple(self, events):
        expected_events = self._cook_events_params(events)
        try:
            self.assert_events_occured(expected_events)
            return
        except AssertionError:
            pass

        done = trio.Event()

        def _waiter(cooked_event):
            try:
                self.assert_events_occured(expected_events)
                self._waiters.remove(_waiter)
                done.set()
            except AssertionError:
                pass

        self._waiters.add(_waiter)
        await done.wait()

    def _cook_events_params(self, events):
        cooked_events = [self._cook_event_params(event) for event in events]
        return cooked_events

    def _cook_event_params(self, event):
        if isinstance(event, SpiedEvent):
            return event
        elif event is ANY:
            return event
        elif isinstance(event, str):
            return SpiedEvent(event, ANY, ANY)
        elif isinstance(event, tuple):
            event = event + (ANY,) * (3 - len(event))
            return SpiedEvent(*event)
        else:
            raise ValueError(
                "event must be provided as `SpiedEvent`, `(<event>, <kwargs>, <dt>)` tuple "
                "or string"
            )

    def assert_event_occured(self, event, dt=ANY, kwargs=ANY):
        expected = SpiedEvent(event, kwargs, dt)
        for occured in self.events:
            if occured == expected:
                break
        else:
            raise AssertionError(f"Event {expected} didn't occured")

    def assert_events_occured(self, events):
        expected_events = self._cook_events_params(events)
        occured_events = iter(self.events)
        try:
            for i, expected in enumerate(expected_events):
                while True:
                    occured = next(occured_events)
                    if occured == expected:
                        break
        except StopIteration:
            raise AssertionError("Missing events: " + "\n".join([str(x) for x in events[i:]]))

    def assert_events_exactly_occured(self, events):
        events = self._cook_events_params(events)
        assert self.events == events


class SpiedEventBus(EventBus):
    ANY = ANY  # Easier to use than doing an import

    def __init__(self):
        super().__init__()
        self._spies = []
        self.spy = self.create_spy()

    def send(self, event, **kwargs):
        for spy in self._spies:
            spy._on_event_cb(event, **kwargs)
        super().send(event, **kwargs)

    def create_spy(self):
        spy = EventBusSpy()
        self._spies.append(spy)
        return spy

    def destroy_spy(self, spy):
        self._spies.remove(spy)

    @contextmanager
    def listen(self):
        spy = self.create_spy()
        yield spy
        self.destroy_spy(spy)
