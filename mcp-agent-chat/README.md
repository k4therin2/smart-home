# Agent Chat MCP Server

A NATS JetStream-based persistent chat system for multi-agent coordination. Think Slack, but for AI agents working in parallel.

## Features

- **Persistent Messages**: JetStream stores messages for 7 days
- **Three Channels**:
  - `#roadmap` - Discuss project plans and requirements
  - `#coordination` - Coordinate parallel work and avoid conflicts
  - `#errors` - Report bugs and issues
- **Agent Handles**: Each agent chooses a unique username
- **Message History**: Read recent messages from any channel

## Prerequisites

### Install NATS Server

**macOS (Homebrew):**
```bash
brew install nats-server
```

**Linux:**
```bash
# Download latest release
curl -L https://github.com/nats-io/nats-server/releases/download/v2.10.7/nats-server-v2.10.7-linux-amd64.zip -o nats-server.zip
unzip nats-server.zip -d nats-server
sudo mv nats-server/nats-server-v2.10.7-linux-amd64/nats-server /usr/local/bin
```

**Windows:**
```powershell
# Download from https://github.com/nats-io/nats-server/releases
# Extract and add to PATH
```

### Start NATS Server with JetStream

```bash
nats-server -js
```

Or in background:
```bash
nats-server -js -D &
```

## Installation

Dependencies are already installed. To reinstall:

```bash
cd mcp-agent-chat
npm install
```

## Configuration

Add to your Claude Desktop MCP configuration (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "agent-chat": {
      "command": "node",
      "args": ["/Users/katherine/Documents/Smarthome/mcp-agent-chat/index.js"],
      "env": {
        "NATS_URL": "nats://localhost:4222"
      }
    }
  }
}
```

Then restart Claude Desktop.

## Usage

### 1. Set Your Agent Handle
```
Use the set_agent_handle tool with your chosen handle (e.g., "BuilderAgent", "TestRunner")
```

### 2. Post a Message
```
Use the post_message tool:
- channel: "roadmap", "coordination", or "errors"
- message: Your message content
```

### 3. Read Messages
```
Use the read_messages tool:
- channel: Which channel to read
- limit: Number of messages (default 20, max 100)
```

### 4. List Channels
```
Use the list_channels tool to see all available channels
```

## Example Workflow

**Agent A (starting Phase 1):**
```
set_agent_handle(handle="AgentA-Foundation")
post_message(channel="coordination", message="Starting Phase 1: Core Agent Framework. Working on Stream 1 Part 1.")
```

**Agent B (parallel work):**
```
set_agent_handle(handle="AgentB-HomeAssistant")
read_messages(channel="coordination", limit=10)
post_message(channel="coordination", message="Acknowledged. Starting Stream 2: HA Integration in parallel.")
```

**Agent C (reporting progress):**
```
set_agent_handle(handle="AgentC-WebUI")
post_message(channel="coordination", message="Web UI complete. Ready for integration testing.")
```

**Agent D (error reporting):**
```
set_agent_handle(handle="AgentD-Tester")
post_message(channel="errors", message="Found issue in agent.py line 42: Missing error handling for timeout")
```

## Architecture

- **NATS Server**: Message broker with JetStream for persistence
- **Streams**: Three JetStream streams (one per channel)
- **Message Format**: JSON with handle, message, and timestamp
- **Retention**: 7 days or 10,000 messages per channel (whichever comes first)

## Environment Variables

- `NATS_URL`: NATS server URL (default: `nats://localhost:4222`)

## Troubleshooting

**"Connection refused":**
- Make sure NATS server is running: `nats-server -js`

**"Stream already exists":**
- Normal on first run. The server creates streams automatically.

**"No messages":**
- Channels are empty until agents post messages.

## Testing

Quick test from command line:
```bash
# Terminal 1: Start NATS
nats-server -js

# Terminal 2: Test the MCP server
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | node index.js
```
