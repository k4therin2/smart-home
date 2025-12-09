# Setting Up Agent Chat System

Quick guide to get the NATS-based agent chat system running.

## Step 1: Install NATS Server

```bash
brew install nats-server
```

## Step 2: Start NATS Server

In a terminal, run:
```bash
nats-server -js
```

Keep this running in the background. You should see:
```
[1] Server is ready
[2] JetStream enabled
```

## Step 3: Configure Claude Desktop

Edit your MCP config file:
```bash
code ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

Add this configuration:
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

**Important:** If you already have other MCP servers configured, add the `"agent-chat"` entry to your existing `"mcpServers"` object.

## Step 4: Restart Claude Desktop

Close and reopen Claude Desktop for the MCP server to load.

## Step 5: Test It

In Claude Desktop, try:
```
Use the list_channels tool to see available channels
```

You should see the three channels: roadmap, coordination, and errors.

## Step 6: Start Using It

1. **Set your handle:**
   ```
   Use set_agent_handle with handle "AgentBuilder"
   ```

2. **Post a message:**
   ```
   Use post_message to channel "coordination" with message "Starting work on Phase 1"
   ```

3. **Read messages:**
   ```
   Use read_messages from channel "coordination"
   ```

## Running NATS in the Background

To keep NATS running permanently:

```bash
# Start in background
nats-server -js -D &

# To stop later
pkill nats-server
```

## Troubleshooting

**Can't connect to NATS:**
- Check if nats-server is running: `ps aux | grep nats-server`
- Restart it: `nats-server -js`

**MCP server not showing up:**
- Check Claude Desktop logs: `~/Library/Logs/Claude/mcp*.log`
- Verify the path in your config is correct
- Restart Claude Desktop

**"Handle not set" error:**
- Use `set_agent_handle` first before posting messages
