#!/usr/bin/env python3
"""NATS client for Project Manager agent."""
import asyncio
import sys
from datetime import datetime
from nats.aio.client import Client as NATS

NATS_URL = 'nats://100.75.232.36:4222'
HANDLE = 'Agent-ProjectManager'

async def set_handle_and_announce():
    """Set agent handle and announce presence."""
    nc = NATS()
    await nc.connect(NATS_URL)

    await nc.publish('agent.handle.set', HANDLE.encode())
    await nc.publish('coordination', f'{HANDLE}: Project Manager online. Beginning roadmap gardening.'.encode())

    await nc.flush()
    await nc.close()
    print(f'{HANDLE} connected and announced')

async def read_channel(channel: str, timeout: float = 2.0):
    """Read recent messages from a channel."""
    nc = NATS()
    await nc.connect(NATS_URL)

    messages = []

    async def message_handler(msg):
        messages.append(msg.data.decode())

    # Try to get last messages (JetStream would be better for this)
    sub = await nc.subscribe(channel, cb=message_handler)

    # Wait briefly for any messages
    await asyncio.sleep(timeout)

    await sub.unsubscribe()
    await nc.close()

    return messages

async def post_message(channel: str, message: str):
    """Post a message to a channel."""
    nc = NATS()
    await nc.connect(NATS_URL)

    await nc.publish(channel, message.encode())
    await nc.flush()
    await nc.close()
    print(f'Posted to #{channel}: {message[:100]}...' if len(message) > 100 else f'Posted to #{channel}: {message}')

async def read_all_channels():
    """Read all relevant channels and return summary."""
    channels = ['coordination', 'errors', 'roadmap', 'smarthome', 'watchdog']
    results = {}

    nc = NATS()
    await nc.connect(NATS_URL)

    for channel in channels:
        results[channel] = []

        async def make_handler(ch):
            async def handler(msg):
                results[ch].append(msg.data.decode())
            return handler

        sub = await nc.subscribe(channel, cb=await make_handler(channel))

    # Wait for messages
    await asyncio.sleep(3.0)

    await nc.close()

    return results

def main():
    if len(sys.argv) < 2:
        print('Usage: pm_nats_client.py <command> [args]')
        print('Commands:')
        print('  announce - Set handle and announce presence')
        print('  read <channel> - Read from a channel')
        print('  read_all - Read from all channels')
        print('  post <channel> <message> - Post to a channel')
        sys.exit(1)

    command = sys.argv[1]

    if command == 'announce':
        asyncio.run(set_handle_and_announce())
    elif command == 'read':
        if len(sys.argv) < 3:
            print('Error: channel required')
            sys.exit(1)
        channel = sys.argv[2]
        messages = asyncio.run(read_channel(channel))
        print(f'Messages from #{channel}:')
        for msg in messages:
            print(f'  - {msg}')
        if not messages:
            print('  (no recent messages)')
    elif command == 'read_all':
        results = asyncio.run(read_all_channels())
        for channel, messages in results.items():
            print(f'\n#{channel}:')
            for msg in messages:
                print(f'  - {msg}')
            if not messages:
                print('  (no recent messages)')
    elif command == 'post':
        if len(sys.argv) < 4:
            print('Error: channel and message required')
            sys.exit(1)
        channel = sys.argv[2]
        message = ' '.join(sys.argv[3:])
        asyncio.run(post_message(channel, message))
    else:
        print(f'Unknown command: {command}')
        sys.exit(1)

if __name__ == '__main__':
    main()
