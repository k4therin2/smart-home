#!/usr/bin/env python3
"""NATS client for User Assistant agent."""
import asyncio
import json
import sys
from datetime import datetime
from nats.aio.client import Client as NATS
from nats.js.api import ConsumerConfig, DeliverPolicy

NATS_URL = 'nats://100.75.232.36:4222'
HANDLE = 'Agent-UserAssistant'

CHANNELS = {
    "coordination": "AGENT_CHAT_COORDINATION",
    "errors": "AGENT_CHAT_ERRORS",
    "roadmap": "AGENT_CHAT_ROADMAP",
    "smarthome": "AGENT_CHAT_SMARTHOME",
}

async def post_message(channel: str, message: str):
    """Post a message to a JetStream channel."""
    nc = NATS()
    await nc.connect(NATS_URL)
    js = nc.jetstream()

    subject = f"agent-chat.{channel}"
    payload = {
        "handle": HANDLE,
        "message": message,
        "timestamp": datetime.now().isoformat()
    }
    await js.publish(subject, json.dumps(payload).encode())
    await nc.close()
    print(f'Posted to #{channel}: {message[:100]}...' if len(message) > 100 else f'Posted to #{channel}: {message}')

async def read_channel(channel: str, limit: int = 50):
    """Read recent messages from a JetStream channel."""
    nc = NATS()
    await nc.connect(NATS_URL)
    js = nc.jetstream()

    messages = []
    stream_name = CHANNELS.get(channel, f"AGENT_CHAT_{channel.upper()}")

    try:
        stream = await js.stream_info(stream_name)

        if stream.state.messages == 0:
            await nc.close()
            return messages

        consumer = await js.pull_subscribe(
            f"agent-chat.{channel}",
            stream=stream_name,
            config=ConsumerConfig(
                deliver_policy=DeliverPolicy.ALL,
                ack_policy="explicit",
            )
        )

        try:
            batch = await consumer.fetch(limit, timeout=5)
            for msg in batch:
                try:
                    data = json.loads(msg.data.decode())
                    messages.append(data)
                    await msg.ack()
                except json.JSONDecodeError:
                    messages.append({"raw": msg.data.decode()})
                    await msg.ack()
        except Exception as e:
            if "timeout" not in str(e).lower():
                print(f"Error fetching: {e}")
    except Exception as e:
        print(f"Channel error: {e}")

    await nc.close()
    return messages

def main():
    if len(sys.argv) < 2:
        print('Usage: ua_nats_client.py <command> [args]')
        print('Commands:')
        print('  read <channel> [limit] - Read from a channel')
        print('  post <channel> <message> - Post to a channel')
        sys.exit(1)

    command = sys.argv[1]

    if command == 'read':
        if len(sys.argv) < 3:
            print('Error: channel required')
            sys.exit(1)
        channel = sys.argv[2]
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 50
        messages = asyncio.run(read_channel(channel, limit))
        for msg in messages:
            if "raw" in msg:
                print(f"[raw] {msg['raw']}")
            else:
                ts = msg.get("timestamp", "")[:19].replace("T", " ")
                handle = msg.get("handle", "unknown")
                text = msg.get("message", str(msg))
                print(f"[{ts}] {handle}: {text}")
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
