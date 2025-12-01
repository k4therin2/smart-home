#!/usr/bin/env python3
"""
Prompt Review Agent - Validates prompt changes for quality and safety

This agent reviews proposed prompt changes before they're saved, checking for:
- Prompt engineering best practices
- Security issues (prompt injection, jailbreaks)
- Template formatting issues
- Clarity and completeness
"""

import os
import json
from typing import Dict, List
from anthropic import Anthropic
from config import MODEL_NAME
from utils import track_api_usage, extract_json_from_markdown


class PromptReviewAgent:
    """
    Specialist agent that reviews prompt changes for quality and safety.
    """

    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = MODEL_NAME

        self.review_prompt = """You are a prompt engineering expert reviewing changes to agent system prompts.

Your task: Analyze the proposed prompt for issues and best practices.

Check for:

1. **Clarity**: Is the prompt clear and unambiguous?
2. **Completeness**: Does it provide enough context and instructions?
3. **Security**: Could it be vulnerable to prompt injection or jailbreaking?
4. **Template Formatting**: For templates with placeholders like {room}, are they used correctly?
5. **Specificity**: Is it specific enough to guide behavior without being overly restrictive?
6. **Consistency**: Does it align with the role (main agent vs specialist)?
7. **Length**: Is it too short (lacking detail) or too long (overwhelming)?

Categorize issues as:
- **CRITICAL**: Must be fixed (security issues, broken templates)
- **WARNING**: Should be reviewed (unclear instructions, potential problems)
- **SUGGESTION**: Could be improved (style, best practices)

Return ONLY JSON:
{
  "approved": true/false,
  "issues": [
    {
      "severity": "CRITICAL" | "WARNING" | "SUGGESTION",
      "category": "clarity" | "completeness" | "security" | "template" | "specificity" | "consistency" | "length",
      "message": "Description of the issue",
      "suggestion": "How to fix it (optional)"
    }
  ],
  "summary": "Brief overall assessment"
}

If there are no issues, return:
{
  "approved": true,
  "issues": [],
  "summary": "Prompt looks good"
}

CRITICAL issues should set approved=false. Warnings and suggestions can still be approved=true.
"""

    def review_prompt_change(self, agent_name: str, prompt_type: str, old_prompt: str, new_prompt: str) -> Dict:
        """
        Review a proposed prompt change.

        Args:
            agent_name: Name of the agent (e.g., "main_agent", "hue_specialist")
            prompt_type: Type of prompt (e.g., "system", "fire_flicker")
            old_prompt: Original prompt text
            new_prompt: Proposed new prompt text

        Returns:
            Dictionary with review results
        """
        # Build the review request
        request = f"""Agent: {agent_name}
Prompt Type: {prompt_type}

OLD PROMPT:
```
{old_prompt[:1000] if old_prompt else "(empty)"}
```

NEW PROMPT:
```
{new_prompt[:1000]}
```

Please review the NEW PROMPT and identify any issues."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=self.review_prompt,
                messages=[{"role": "user", "content": request}]
            )

            # Track API usage
            if hasattr(response, 'usage'):
                track_api_usage(
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens
                )

            # Parse JSON response
            response_text = response.content[0].text.strip()

            # Remove markdown code blocks using robust utility function
            clean_json = extract_json_from_markdown(response_text)

            review_result = json.loads(clean_json)

            return {
                "success": True,
                "review": review_result
            }

        except json.JSONDecodeError as e:
            # Fallback if agent returns invalid JSON
            return {
                "success": True,
                "review": {
                    "approved": True,
                    "issues": [{
                        "severity": "WARNING",
                        "category": "system",
                        "message": f"Review agent returned invalid JSON: {str(e)}",
                        "suggestion": "Proceeding with save, but review manually"
                    }],
                    "summary": "Unable to fully validate (review agent error)"
                }
            }

        except Exception as e:
            # Fallback for other errors
            return {
                "success": False,
                "error": f"Review agent error: {str(e)}"
            }

    def review_all_changes(self, old_prompts: Dict, new_prompts: Dict) -> Dict:
        """
        Review all changes between old and new prompt configurations.

        Args:
            old_prompts: Original prompts
            new_prompts: Proposed new prompts

        Returns:
            Dictionary with overall review results
        """
        all_reviews = {}
        has_critical = False
        total_issues = 0

        # Check main_agent changes
        if "main_agent" in new_prompts:
            for key in ["system"]:
                old_val = old_prompts.get("main_agent", {}).get(key, "")
                new_val = new_prompts["main_agent"].get(key, "")

                if old_val != new_val:
                    review = self.review_prompt_change("main_agent", key, old_val, new_val)
                    if review["success"]:
                        all_reviews[f"main_agent.{key}"] = review["review"]
                        if not review["review"].get("approved", True):
                            has_critical = True
                        total_issues += len(review["review"].get("issues", []))

        # Check hue_specialist changes
        if "hue_specialist" in new_prompts:
            for key in ["system", "fire_flicker", "effect_mapping"]:
                old_val = old_prompts.get("hue_specialist", {}).get(key, "")
                new_val = new_prompts["hue_specialist"].get(key, "")

                if old_val != new_val:
                    review = self.review_prompt_change("hue_specialist", key, old_val, new_val)
                    if review["success"]:
                        all_reviews[f"hue_specialist.{key}"] = review["review"]
                        if not review["review"].get("approved", True):
                            has_critical = True
                        total_issues += len(review["review"].get("issues", []))

        return {
            "success": True,
            "approved": not has_critical,
            "reviews": all_reviews,
            "total_issues": total_issues,
            "summary": f"Reviewed {len(all_reviews)} changes, found {total_issues} issues" if all_reviews else "No changes detected"
        }


# Singleton instance
_review_agent = None

def get_review_agent() -> PromptReviewAgent:
    """Get the singleton review agent."""
    global _review_agent
    if _review_agent is None:
        _review_agent = PromptReviewAgent()
    return _review_agent
