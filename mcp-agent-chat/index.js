#!/usr/bin/env node

/**
 * NATS JetStream Agent Chat MCP Server
 * Provides Slack-like persistent chat channels for multi-agent coordination
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { connect, StringCodec } from "nats";
import { z } from "zod";

const sc = StringCodec();

// Configuration
const NATS_URL = process.env.NATS_URL || "nats://localhost:4222";
const CHANNELS = {
  roadmap: "agent-chat.roadmap",
  coordination: "agent-chat.coordination",
  errors: "agent-chat.errors",
};

// Global state
let natsConnection = null;
let jetStream = null;
let agentHandle = null;

// Connect to NATS
async function connectNATS() {
  if (!natsConnection) {
    natsConnection = await connect({ servers: NATS_URL });
    jetStream = natsConnection.jetstream();

    // Create streams for each channel if they don't exist
    const jsm = await natsConnection.jetstreamManager();

    for (const [name, subject] of Object.entries(CHANNELS)) {
      try {
        await jsm.streams.add({
          name: `AGENT_CHAT_${name.toUpperCase()}`,
          subjects: [subject],
          retention: "limits",
          max_msgs: 10000,
          max_age: 7 * 24 * 60 * 60 * 1000000000, // 7 days in nanoseconds
          storage: "file",
        });
      } catch (err) {
        // Stream might already exist
        if (!err.message.includes("already in use")) {
          console.error(`Error creating stream for ${name}:`, err.message);
        }
      }
    }
  }
  return { natsConnection, jetStream };
}

// Tool schemas
const SetHandleSchema = z.object({
  handle: z.string().min(1).max(50).describe("Your agent handle/username"),
});

const PostMessageSchema = z.object({
  channel: z.enum(["roadmap", "coordination", "errors"]).describe("Channel to post in"),
  message: z.string().min(1).describe("Message content"),
});

const ReadMessagesSchema = z.object({
  channel: z.enum(["roadmap", "coordination", "errors"]).describe("Channel to read from"),
  limit: z.number().int().positive().max(100).default(20).describe("Number of recent messages to retrieve"),
});

const ListChannelsSchema = z.object({});

// MCP Server
const server = new Server(
  {
    name: "agent-chat",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// List available tools
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "set_agent_handle",
        description: "Set your agent handle/username for posting messages. Choose a unique identifier.",
        inputSchema: {
          type: "object",
          properties: {
            handle: {
              type: "string",
              description: "Your agent handle/username (e.g., 'AgentA', 'BuilderBot', 'TestRunner')",
              minLength: 1,
              maxLength: 50,
            },
          },
          required: ["handle"],
        },
      },
      {
        name: "post_message",
        description: "Post a message to a channel. You must set your handle first using set_agent_handle.",
        inputSchema: {
          type: "object",
          properties: {
            channel: {
              type: "string",
              enum: ["roadmap", "coordination", "errors"],
              description: "Channel: 'roadmap' (discussing plans), 'coordination' (parallel work sync), 'errors' (bug reports)",
            },
            message: {
              type: "string",
              description: "Message content",
              minLength: 1,
            },
          },
          required: ["channel", "message"],
        },
      },
      {
        name: "read_messages",
        description: "Read recent messages from a channel",
        inputSchema: {
          type: "object",
          properties: {
            channel: {
              type: "string",
              enum: ["roadmap", "coordination", "errors"],
              description: "Channel to read from",
            },
            limit: {
              type: "number",
              description: "Number of recent messages to retrieve (default: 20, max: 100)",
              default: 20,
              minimum: 1,
              maximum: 100,
            },
          },
          required: ["channel"],
        },
      },
      {
        name: "list_channels",
        description: "List all available channels and their descriptions",
        inputSchema: {
          type: "object",
          properties: {},
        },
      },
    ],
  };
});

// Handle tool calls
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    await connectNATS();

    switch (name) {
      case "set_agent_handle": {
        const { handle } = SetHandleSchema.parse(args);
        agentHandle = handle;
        return {
          content: [
            {
              type: "text",
              text: `Agent handle set to: ${handle}\nYou can now post messages to channels.`,
            },
          ],
        };
      }

      case "post_message": {
        const { channel, message } = PostMessageSchema.parse(args);

        if (!agentHandle) {
          return {
            content: [
              {
                type: "text",
                text: "Error: You must set your agent handle first using set_agent_handle.",
              },
            ],
            isError: true,
          };
        }

        const subject = CHANNELS[channel];
        const payload = {
          handle: agentHandle,
          message,
          timestamp: new Date().toISOString(),
        };

        await jetStream.publish(subject, sc.encode(JSON.stringify(payload)));

        return {
          content: [
            {
              type: "text",
              text: `Message posted to #${channel} by ${agentHandle}:\n"${message}"`,
            },
          ],
        };
      }

      case "read_messages": {
        const { channel, limit = 20 } = ReadMessagesSchema.parse(args);

        const subject = CHANNELS[channel];
        const streamName = `AGENT_CHAT_${channel.toUpperCase()}`;

        // Create consumer to read messages
        const jsm = await natsConnection.jetstreamManager();
        const consumerName = `reader-${Date.now()}`;

        try {
          await jsm.consumers.add(streamName, {
            durable_name: consumerName,
            deliver_policy: "last_per_subject",
            ack_policy: "explicit",
          });

          const consumer = await jetStream.consumers.get(streamName, consumerName);
          const messages = [];

          const iter = await consumer.fetch({ max_messages: limit });
          for await (const msg of iter) {
            try {
              const data = JSON.parse(sc.decode(msg.data));
              messages.push(data);
              msg.ack();
            } catch (err) {
              console.error("Error parsing message:", err);
              msg.ack();
            }
          }

          // Clean up consumer
          await jsm.consumers.delete(streamName, consumerName);

          if (messages.length === 0) {
            return {
              content: [
                {
                  type: "text",
                  text: `No messages in #${channel} yet.`,
                },
              ],
            };
          }

          // Format messages
          const formattedMessages = messages
            .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
            .map((msg) => {
              const time = new Date(msg.timestamp).toLocaleString();
              return `[${time}] ${msg.handle}: ${msg.message}`;
            })
            .join("\n");

          return {
            content: [
              {
                type: "text",
                text: `Recent messages in #${channel}:\n\n${formattedMessages}`,
              },
            ],
          };
        } catch (err) {
          return {
            content: [
              {
                type: "text",
                text: `Error reading messages: ${err.message}`,
              },
            ],
            isError: true,
          };
        }
      }

      case "list_channels": {
        const channelList = `Available channels:

📋 #roadmap
   Discuss project roadmap, requirements, and planning

🔄 #coordination
   Coordinate parallel work, avoid conflicts, share status updates

❌ #errors
   Report bugs, errors, and issues that need attention

Use post_message to send messages and read_messages to view history.`;

        return {
          content: [
            {
              type: "text",
              text: channelList,
            },
          ],
        };
      }

      default:
        return {
          content: [
            {
              type: "text",
              text: `Unknown tool: ${name}`,
            },
          ],
          isError: true,
        };
    }
  } catch (error) {
    return {
      content: [
        {
          type: "text",
          text: `Error: ${error.message}`,
        },
      ],
      isError: true,
    };
  }
});

// Start server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Agent Chat MCP Server running on stdio");
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
