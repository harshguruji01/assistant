"""
Unit tests for asynchronous typed event bus.
"""

import asyncio
import unittest
from falcon.core.event_bus import Event, EventBus, EventNames


class TestEventBus(unittest.TestCase):

    def setUp(self):
        self.bus = EventBus()

    def test_publish_subscribe(self):
        received = []

        async def _test():
            def handler(event: Event):
                received.append(event.data)

            self.bus.subscribe(EventNames.ASSISTANT_READY, handler)
            await self.bus.publish(Event(topic=EventNames.ASSISTANT_READY, data={"status": "online"}))

        asyncio.run(_test())
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["status"], "online")

    def test_wildcard_subscription(self):
        received_topics = []

        async def _test():
            def handler(event: Event):
                received_topics.append(event.topic)

            self.bus.subscribe("task.*", handler)
            await self.bus.publish(Event(topic=EventNames.TASK_CREATED, data={"id": 1}))
            await self.bus.publish(Event(topic=EventNames.TASK_PROGRESS, data={"id": 1}))
            await self.bus.publish(Event(topic=EventNames.ASSISTANT_READY, data={}))

        asyncio.run(_test())
        self.assertEqual(received_topics, [EventNames.TASK_CREATED, EventNames.TASK_PROGRESS])

    def test_handler_error_isolation(self):
        results = []

        async def _test():
            def faulty_handler(event: Event):
                raise RuntimeError("Faulty listener")

            def good_handler(event: Event):
                results.append("success")

            self.bus.subscribe("test.topic", faulty_handler)
            self.bus.subscribe("test.topic", good_handler)

            await self.bus.publish(Event(topic="test.topic"))

        asyncio.run(_test())
        self.assertEqual(results, ["success"])


if __name__ == "__main__":
    unittest.main()
