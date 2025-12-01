#!/usr/bin/env python3
"""
Prompt Improvement Agent - AI chatbot assistant for improving prompts

This agent helps users iteratively improve their agent prompts through conversation.
Users can describe what's not working, and the agent suggests improved versions.
"""

import os
import json
from typing import Dict, List, Any
from anthropic import Anthropic
from utils import track_api_usage, load_prompts


# TODO: Implement context compression for long chat histories
# Consider using tiktoken or similar to keep under token limits
# For now, we keep last 10 messages (common practice, ~2-3K tokens)
MAX_CHAT_HISTORY = 10


class PromptImprovementAgent:
    """
    AI chatbot that helps users improve their prompts through conversation.

    Features:
    - Multi-turn conversation with reasonable lookback
    - Code context awareness (metadata, tools, usage patterns)
    - Suggests improvements based on user feedback
    - Best practices enforcement
    """

    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-20250514"

        self.system_prompt = """# Prompt Engineering Assistant

You are an expert prompt engineering assistant helping users improve their AI agent prompts.

## Your Role

Help users iteratively refine their agent system prompts through conversation. Users will describe:
- What's not working with current behavior
- What they want to change or improve
- Specific issues they're encountering

You will suggest improved prompt versions with clear reasoning.

## Context You Have Access To

You'll be provided with:
- **Current prompt text** - What the prompt currently says
- **Agent metadata** - When this agent is called, its purpose, available tools, examples
- **User feedback** - What the user wants to improve
- **Chat history** - Previous conversation turns for context

## Your Responsibilities

1. **Understand the Problem**: Ask clarifying questions if the user's feedback is vague
2. **Provide Context-Aware Suggestions**: Consider how the prompt is used in the larger system
3. **Apply Best Practices**:
   - Clear, specific instructions
   - Appropriate level of detail (not too short, not overwhelming)
   - Good formatting and structure
   - Security considerations (avoid prompt injection vulnerabilities)
   - Consistency with the agent's role and capabilities

4. **Explain Your Reasoning**: Always explain WHY you're suggesting changes
5. **Iterate**: Be ready for follow-up refinement

## Response Format

When suggesting a prompt improvement, return ONLY JSON in this format:

```json
{
  "suggested_prompt": "<the improved prompt text>",
  "reasoning": "<explanation of what you changed and why>",
  "key_changes": [
    "Change 1: description",
    "Change 2: description"
  ],
  "considerations": "<any important notes or trade-offs the user should know>"
}
```

When asking clarifying questions or having a conversation (not making a suggestion yet), return:

```json
{
  "message": "<your question or response>",
  "needs_clarification": true
}
```

## Important Guidelines

- **Preserve Intent**: Don't change the core purpose unless explicitly asked
- **Stay Focused**: Only address what the user mentioned - don't over-engineer
- **Be Specific**: Vague improvements like "make it better" aren't helpful
- **Consider Context**: Remember this prompt works with specific tools and other agents
- **Security First**: Flag any potential security issues you notice

## Example Interaction

User: "The fire effect isn't working well. It's using too many API calls."

You should suggest moving from software-based flickering to hardware-based Hue scenes, explain the performance benefits (1 call vs 11+ calls), and show how to update the prompt to prefer native scenes.

User: "The agent doesn't understand 'under the sea'"

You should suggest adding example mappings or improving the guidance for abstract descriptions, explaining how this helps the agent interpret creative requests.
"""

    def _get_code_context(self, agent_name: str) -> str:
        """
        Extract relevant code context for the agent being edited.

        Args:
            agent_name: Name of the agent (main_agent or hue_specialist)

        Returns:
            Formatted code context string
        """
        # Import metadata from agents
        try:
            if agent_name == "main_agent":
                from agent import METADATA
            elif agent_name == "hue_specialist":
                from tools.hue_specialist import METADATA
            else:
                return "No metadata available"

            context = f"""## Agent: {METADATA['name']} {METADATA['icon']}

**When Called**: {METADATA['when_called']}

**Purpose**: {METADATA['purpose']}

**Available Tools**:
{chr(10).join(f"- {tool}" for tool in METADATA.get('tools_available', []))}
"""

            if 'can_delegate_to' in METADATA:
                context += f"\n**Can Delegate To**: {', '.join(METADATA['can_delegate_to'])}\n"

            if 'examples' in METADATA:
                context += f"\n**Example Usage**:\n"
                context += chr(10).join(f"- {ex}" for ex in METADATA['examples'])

            return context

        except Exception as e:
            return f"Error loading metadata: {str(e)}"

    def chat(
        self,
        agent_name: str,
        prompt_type: str,
        current_prompt: str,
        user_message: str,
        chat_history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Have a conversation with the user about improving a prompt.

        Args:
            agent_name: Name of the agent (e.g., "main_agent", "hue_specialist")
            prompt_type: Type of prompt (e.g., "system")
            current_prompt: Current prompt text
            user_message: User's latest message/feedback
            chat_history: Previous conversation turns (list of {role, content} dicts)

        Returns:
            Dictionary with agent response (either suggestion or clarifying question)
        """
        if chat_history is None:
            chat_history = []

        # Limit chat history to last N messages to avoid token overflow
        # TODO: Implement smarter context compression here
        if len(chat_history) > MAX_CHAT_HISTORY:
            chat_history = chat_history[-MAX_CHAT_HISTORY:]

        # Get code context for this agent
        code_context = self._get_code_context(agent_name)

        # Build the initial context message
        context_message = f"""I'm helping you improve the **{agent_name}.{prompt_type}** prompt.

{code_context}

---

**Current Prompt**:
```
{current_prompt[:1000]}{"..." if len(current_prompt) > 1000 else ""}
```

---

Now, let's work on improving it based on your feedback!"""

        # Build messages array
        messages = []

        # If this is the first message, include context
        if not chat_history:
            messages.append({"role": "user", "content": context_message})
            messages.append({"role": "assistant", "content": "I understand the current prompt and context. What would you like to improve or change?"})
        else:
            # Include chat history
            messages.extend(chat_history)

        # Add the user's current message
        messages.append({"role": "user", "content": user_message})

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=self.system_prompt,
                messages=messages
            )

            # Track API usage
            if hasattr(response, 'usage'):
                track_api_usage(
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens
                )

            # Parse response
            response_text = response.content[0].text.strip()

            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                # Find the end of the opening code fence
                start_idx = 1
                if lines[0].startswith("```json"):
                    start_idx = 1
                # Find the closing fence
                end_idx = len(lines) - 1
                for i in range(len(lines) - 1, 0, -1):
                    if lines[i].strip().startswith("```"):
                        end_idx = i
                        break
                response_text = "\n".join(lines[start_idx:end_idx])

            result = json.loads(response_text)

            return {
                "success": True,
                "response": result,
                "chat_history": messages + [{"role": "assistant", "content": response_text}]
            }

        except json.JSONDecodeError as e:
            # If JSON parsing fails, return the raw text as a message
            return {
                "success": True,
                "response": {
                    "message": response_text,
                    "needs_clarification": False
                },
                "chat_history": messages + [{"role": "assistant", "content": response_text}]
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Chat error: {str(e)}"
            }

    def suggest_improvement(
        self,
        agent_name: str,
        prompt_type: str,
        current_prompt: str,
        user_feedback: str
    ) -> Dict[str, Any]:
        """
        One-shot improvement suggestion (no chat history).

        This is a convenience method for when the user just wants a quick suggestion
        without iterative refinement.

        Args:
            agent_name: Name of the agent
            prompt_type: Type of prompt
            current_prompt: Current prompt text
            user_feedback: What the user wants to improve

        Returns:
            Dictionary with suggested prompt and reasoning
        """
        result = self.chat(
            agent_name=agent_name,
            prompt_type=prompt_type,
            current_prompt=current_prompt,
            user_message=user_feedback,
            chat_history=None
        )

        return result


# Singleton instance
_improvement_agent = None

def get_improvement_agent() -> PromptImprovementAgent:
    """Get the singleton improvement agent."""
    global _improvement_agent
    if _improvement_agent is None:
        _improvement_agent = PromptImprovementAgent()
    return _improvement_agent
