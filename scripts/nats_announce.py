#!/usr/bin/env python3
"""Announce User Assistant presence on NATS channels."""
import asyncio
from nats.aio.client import Client as NATS

async def main():
    nc = NATS()
    await nc.connect('nats://100.75.232.36:4222')

    # Set agent handle
    await nc.publish('agent.handle.set', b'Agent-UserAssistant')

    # Announce in #smarthome
    await nc.publish('smarthome', b'User Assistant ready. Post your requests, questions, or feedback here.')

    # Also announce in #coordination
    await nc.publish('coordination', b'Agent-UserAssistant: Online and monitoring #smarthome for user requests.')

    await nc.flush()
    await nc.close()
    print('Agent-UserAssistant connected and announced')

if __name__ == '__main__':
    asyncio.run(main())
