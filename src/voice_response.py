"""
Voice Response Formatter

Provides TTS-friendly formatting for voice responses:
- Minimal personality (removes chatty phrases)
- TTS-safe formatting (no special characters, emojis)
- Response truncation for voice output
- Confirmation and error message templates

REQ-016: Voice Control via HA Voice Puck
"""

import re


# Default chatty phrases to remove (minimal personality)
DEFAULT_CHATTY_PHRASES = [
    r"^sure[!,.]?\s*",
    r"^absolutely[!,.]?\s*",
    r"^certainly[!,.]?\s*",
    r"^of course[!,.]?\s*",
    r"^no problem[!,.]?\s*",
    r"^i'?d be happy to[!,.]?\s*",
    r"^i'?d be glad to[!,.]?\s*",
    r"^happy to help[!,.]?\s*",
    r"^great question[!,.]?\s*",
    r"^good question[!,.]?\s*",
    r"^let me[!,.]?\s*",
    r"^okay[!,.]?\s*",
    r"^alright[!,.]?\s*",
    r"^right away[!,.]?\s*",
    r"^you got it[!,.]?\s*",
    r"^you bet[!,.]?\s*",
    r"^for sure[!,.]?\s*",
]

# Emoji pattern (Unicode emoji blocks)
EMOJI_PATTERN = re.compile(
    "["
    "\U0001f600-\U0001f64f"  # emoticons
    "\U0001f300-\U0001f5ff"  # symbols & pictographs
    "\U0001f680-\U0001f6ff"  # transport & map symbols
    "\U0001f700-\U0001f77f"  # alchemical symbols
    "\U0001f780-\U0001f7ff"  # Geometric Shapes
    "\U0001f800-\U0001f8ff"  # Supplemental Arrows-C
    "\U0001f900-\U0001f9ff"  # Supplemental Symbols and Pictographs
    "\U0001fa00-\U0001fa6f"  # Chess Symbols
    "\U0001fa70-\U0001faff"  # Symbols and Pictographs Extended-A
    "\U00002702-\U000027b0"  # Dingbats
    "\U000024c2-\U0001f251"
    "]+",
    flags=re.UNICODE,
)

# Markdown and special character patterns
SPECIAL_CHAR_PATTERNS = [
    (r"\*\*([^*]+)\*\*", r"\1"),  # **bold** -> bold
    (r"\*([^*]+)\*", r"\1"),  # *italic* -> italic
    (r"`([^`]+)`", r"\1"),  # `code` -> code
    (r"\[([^\]]+)\]\([^)]+\)", r"\1"),  # [text](url) -> text
    (r"->|→", " to "),  # arrows
    (r"<-|←", " from "),  # arrows
    (r"•|–|—", ","),  # bullets and dashes to commas
    (r"#+ ", ""),  # Markdown headers
]


class ResponseFormatter:
    """
    Format LLM responses for Text-to-Speech output.

    Removes verbosity, special characters, and ensures responses
    are appropriate for voice output.
    """

    def __init__(self, max_words: int = 100, extra_chatty_phrases: list[str] | None = None):
        """
        Initialize the ResponseFormatter.

        Args:
            max_words: Maximum words in formatted response (default 100)
            extra_chatty_phrases: Additional phrases to filter out
        """
        self.max_words = max_words

        # Compile chatty phrase patterns
        all_phrases = DEFAULT_CHATTY_PHRASES.copy()
        if extra_chatty_phrases:
            for phrase in extra_chatty_phrases:
                # Convert simple phrases to regex patterns
                pattern = r"^" + re.escape(phrase.lower().rstrip("!.,")) + r"[!,.]?\s*"
                all_phrases.append(pattern)

        self.chatty_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in all_phrases]

    def format(self, text: str | None) -> str:
        """
        Format text for TTS output.

        Args:
            text: Raw text from LLM or system

        Returns:
            TTS-friendly formatted string
        """
        if text is None:
            return ""

        if not isinstance(text, str):
            text = str(text)

        result = text.strip()

        if not result:
            return ""

        # Remove chatty phrases at the start
        result = self._remove_chatty_phrases(result)

        # Remove emojis
        result = self._remove_emojis(result)

        # Clean special characters
        result = self._clean_special_chars(result)

        # Normalize whitespace
        result = self._normalize_whitespace(result)

        # Handle multiline (join for speech)
        result = self._join_multiline(result)

        # Truncate if too long
        result = self._truncate(result)

        return result.strip()

    def _remove_chatty_phrases(self, text: str) -> str:
        """Remove chatty/verbose phrases from the start of text."""
        result = text

        # Apply each pattern, allowing multiple passes for nested phrases
        for _ in range(3):  # Max 3 chatty phrases stacked
            original = result
            for pattern in self.chatty_patterns:
                result = pattern.sub("", result, count=1)
            if result == original:
                break

        # Capitalize first letter if we removed something
        if result and result != text:
            result = result[0].upper() + result[1:] if len(result) > 1 else result.upper()

        return result

    def _remove_emojis(self, text: str) -> str:
        """Remove emoji characters."""
        return EMOJI_PATTERN.sub("", text)

    def _clean_special_chars(self, text: str) -> str:
        """Clean markdown and special characters."""
        result = text
        for pattern, replacement in SPECIAL_CHAR_PATTERNS:
            result = re.sub(pattern, replacement, result)
        return result

    def _normalize_whitespace(self, text: str) -> str:
        """Normalize excessive whitespace to single spaces."""
        # Replace multiple spaces with single space
        result = re.sub(r" {2,}", " ", text)
        # Clean up spaces around punctuation
        result = re.sub(r"\s+([.,!?])", r"\1", result)
        result = re.sub(r"([.,!?])\s{2,}", r"\1 ", result)
        return result.strip()

    def _join_multiline(self, text: str) -> str:
        """Join multiline text for speech."""
        # Replace newlines with periods if not already punctuated
        lines = text.split("\n")
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line:
                # Add period if line doesn't end with punctuation
                if line and line[-1] not in ".!?":
                    line += "."
                cleaned_lines.append(line)
        return " ".join(cleaned_lines)

    def _truncate(self, text: str) -> str:
        """Truncate text to max_words, adding ellipsis if truncated."""
        words = text.split()
        if len(words) <= self.max_words:
            return text

        truncated = " ".join(words[: self.max_words])

        # Clean up truncation point
        truncated = truncated.rstrip(".,!?")
        truncated += "..."

        return truncated

    def confirmation(self, subject: str, action: str) -> str:
        """
        Generate a simple confirmation message.

        Args:
            subject: What was affected (e.g., "lights", "temperature")
            action: What happened (e.g., "turned on", "set to 72")

        Returns:
            Concise confirmation string
        """
        return f"{subject.capitalize()} {action}."

    def confirmation_simple(self) -> str:
        """
        Generate a minimal "done" confirmation.

        Returns:
            Simple confirmation string
        """
        return "Done."

    def error(self, technical_error: str) -> str:
        """
        Format a technical error into a user-friendly voice message.

        Args:
            technical_error: Raw error message (may contain technical details)

        Returns:
            Human-friendly error message for voice output
        """
        # Check for common error types and provide friendly messages
        error_lower = technical_error.lower()

        if "connection" in error_lower or "refused" in error_lower:
            return "Sorry, I couldn't connect to the home system. Please try again."

        if "timeout" in error_lower:
            return self.error_timeout()

        if "not found" in error_lower:
            return "Sorry, I couldn't find that device or room."

        if "permission" in error_lower or "unauthorized" in error_lower:
            return "Sorry, I don't have permission to do that."

        if "api" in error_lower:
            return "Sorry, there was a problem with the smart home service."

        # Generic error (don't expose technical details)
        return "Sorry, something went wrong. Please try again."

    def error_timeout(self) -> str:
        """
        Generate a timeout error message.

        Returns:
            Timeout error string for voice output
        """
        return "Sorry, that took too long. Please try again."

    def error_not_understood(self) -> str:
        """
        Generate a "not understood" error message.

        Returns:
            Not understood error string for voice output
        """
        return "Sorry, I didn't understand that. Could you repeat it?"
