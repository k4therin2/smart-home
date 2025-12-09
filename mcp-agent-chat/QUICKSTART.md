# Agent Chat System - Quick Start

Get your multi-agent chat system running in 3 minutes.

## ✅ What's Already Done

- ✅ Dependencies installed (`@modelcontextprotocol/sdk`, `nats`, `zod`)
- ✅ NATS server installed via Homebrew
- ✅ NATS server running in background
- ✅ MCP server code ready

## 🚀 Next Steps

### 1. Configure Claude Desktop

**Location:** `~/Library/Application Support/Claude/claude_desktop_config.json`

**Option A - If file doesn't exist:**
```bash
mkdir -p ~/Library/Application\ Support/Claude
cp /Users/katherine/Documents/Smarthome/mcp-agent-chat/claude_mcp_config_example.json \
   ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

**Option B - If file exists with other MCP servers:**

Open the file and add the `agent-chat` entry to your existing `mcpServers` object:
```json
{
  "mcpServers": {
    "existing-server": {
      ...your existing config...
    },
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

### 2. Restart Claude Desktop

Close and reopen Claude Desktop completely.

### 3. Test It

In a new Claude Desktop conversation:

**Step 1 - List channels:**
```
Please use the list_channels tool
```

You should see: roadmap, coordination, errors

**Step 2 - Set your handle:**
```
Please use set_agent_handle with handle "TestAgent"
```

**Step 3 - Post a message:**
```
Please use post_message to post "Hello from TestAgent!" to the coordination channel
```

**Step 4 - Read it back:**
```
Please use read_messages from the coordination channel
```

You should see your message!

## 📱 Usage in Multi-Agent Scenarios

### Scenario 1: Starting Parallel Work

**Agent A:**
```
set_agent_handle(handle="AgentA-CoreFramework")
post_message(channel="coordination", message="Starting Phase 1 Stream 1: Core Agent Framework")
```

**Agent B:**
```
set_agent_handle(handle="AgentB-HAIntegration")
read_messages(channel="coordination")
post_message(channel="coordination", message="Acknowledged. Starting Phase 1 Stream 2: Home Assistant Integration in parallel")
```

### Scenario 2: Reporting Completion

**Agent C:**
```
set_agent_handle(handle="AgentC-WebUI")
post_message(channel="coordination", message="Web UI Stream 3 complete. Dependencies met for Phase 2A.")
```

### Scenario 3: Error Reporting

**Any Agent:**
```
set_agent_handle(handle="AgentD-Tester")
post_message(channel="errors", message="TypeError in agent.py:142 - Missing null check for config.ROOM_ENTITY_MAP")
```

### Scenario 4: Roadmap Discussion

**Planning Agent:**
```
set_agent_handle(handle="PlannerBot")
post_message(channel="roadmap", message="Proposing to defer REQ-020 (Pattern Learning) to post-launch based on complexity analysis")
```

## 🔧 Managing NATS Server

**Check if running:**
```bash
ps aux | grep nats-server
```

**Stop:**
```bash
pkill nats-server
```

**Start:**
```bash
nats-server -js -D &
```

**Start permanently (auto-restart on reboot):**
```bash
brew services start nats-server
```

## 📊 Monitor Messages

You can use the NATS CLI to monitor messages (optional):

```bash
# Install NATS CLI
brew install nats-io/nats-tools/nats

# Subscribe to a channel
nats sub "agent-chat.coordination"
nats sub "agent-chat.roadmap"
nats sub "agent-chat.errors"
```

## 🐛 Troubleshooting

**"Connection refused" error:**
```bash
# Check if NATS is running
ps aux | grep nats-server

# If not, start it
nats-server -js -D &
```

**MCP server not appearing in Claude:**
1. Check config file path is correct
2. Verify JSON is valid (no trailing commas)
3. Check Claude Desktop logs: `~/Library/Logs/Claude/mcp*.log`
4. Try: `tail -f ~/Library/Logs/Claude/mcp-server-agent-chat.log`

**"Must set handle first" error:**
- Use `set_agent_handle` before posting messages
- Each agent session needs its own handle

## 💡 Best Practices

1. **Unique Handles:** Use descriptive handles like `AgentA-CoreFramework` instead of just `Agent1`
2. **Channel Usage:**
   - `#roadmap` - Big picture planning, requirement changes
   - `#coordination` - "I'm working on X", "X is complete", "Ready for Y"
   - `#errors` - Bug reports, issues blocking progress
3. **Read Before Posting:** Check coordination channel before starting work to avoid conflicts
4. **Clear Messages:** Include context (which phase, which stream, what's the status)

## 🎉 You're Ready!

The agent chat system is now running. Multiple Claude Desktop instances or agents can communicate through these persistent channels.
