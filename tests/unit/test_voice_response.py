"""
ResponseFormatter Unit Tests

Test Strategy:
- Test minimal personality (remove chatty phrases)
- Test TTS-friendly formatting (no special chars, clean punctuation)
- Test response truncation (max length for voice)
- Test confirmation templates
- Test error message formatting

TDD Phase: TESTS FIRST - implementation pending.
"""

import pytest


# =============================================================================
# ResponseFormatter Class Tests
# =============================================================================

class TestResponseFormatter:
    """Tests for ResponseFormatter class in src/voice_response.py."""

    def test_response_formatter_import(self):
        """
        Test that ResponseFormatter can be imported.

        TDD Red Phase: This test should fail until implementation exists.
        """
        from src.voice_response import ResponseFormatter
        assert ResponseFormatter is not None

    def test_response_formatter_instantiation(self):
        """
        Test ResponseFormatter can be instantiated.
        """
        from src.voice_response import ResponseFormatter

        formatter = ResponseFormatter()
        assert formatter is not None

    def test_format_strips_chatty_phrases(self):
        """
        Test that format() removes chatty/verbose phrases.

        Minimal personality requirement: No "Sure!", "Absolutely!",
        "I'd be happy to...", etc.
        """
        from src.voice_response import ResponseFormatter

        formatter = ResponseFormatter()

        chatty_responses = [
            "Sure! I've turned on the lights.",
            "Absolutely! The lights are now on.",
            "I'd be happy to help! The lights are on.",
            "Of course! Done turning on the lights.",
            "Certainly! Lights activated.",
            "No problem! I've adjusted the lights for you.",
        ]

        for chatty in chatty_responses:
            result = formatter.format(chatty)
            # Should not start with these chatty phrases
            assert not result.lower().startswith("sure")
            assert not result.lower().startswith("absolutely")
            assert not result.lower().startswith("i'd be happy")
            assert not result.lower().startswith("of course")
            assert not result.lower().startswith("certainly")
            assert not result.lower().startswith("no problem")
            # Should still contain the actual content
            assert "light" in result.lower()

    def test_format_removes_emojis(self):
        """
        Test that format() removes emojis for TTS compatibility.
        """
        from src.voice_response import ResponseFormatter

        formatter = ResponseFormatter()

        emoji_responses = [
            "Lights on! 💡",
            "Done ✅",
            "🎵 Playing music now",
            "Temperature set to 72°F 🌡️",
        ]

        for emoji_text in emoji_responses:
            result = formatter.format(emoji_text)
            # Should not contain common emojis
            assert "💡" not in result
            assert "✅" not in result
            assert "🎵" not in result
            assert "🌡️" not in result

    def test_format_removes_special_characters_for_tts(self):
        """
        Test that format() cleans special characters that TTS handles poorly.
        """
        from src.voice_response import ResponseFormatter

        formatter = ResponseFormatter()

        # Characters that TTS engines often mispronounce or skip
        special_responses = [
            "Result: **success**",  # Markdown bold
            "See `config.yaml` for details",  # Backticks
            "Options: [a] [b] [c]",  # Brackets
            "Step 1. -> Step 2. -> Done",  # Arrows
        ]

        result1 = formatter.format("Result: **success**")
        assert "**" not in result1
        assert "success" in result1.lower()

        result2 = formatter.format("See `config.yaml` for details")
        assert "`" not in result2
        assert "config" in result2.lower()

    def test_format_truncates_long_responses(self):
        """
        Test that format() truncates responses exceeding max words.

        Max 100 words for voice responses to avoid listener fatigue.
        """
        from src.voice_response import ResponseFormatter

        formatter = ResponseFormatter(max_words=100)

        # Generate a very long response (150+ words)
        long_text = " ".join(["word"] * 150)
        result = formatter.format(long_text)

        word_count = len(result.split())
        assert word_count <= 100

    def test_format_adds_truncation_indicator(self):
        """
        Test that truncated responses indicate more content exists.
        """
        from src.voice_response import ResponseFormatter

        formatter = ResponseFormatter(max_words=10)

        long_text = " ".join(["word"] * 50)
        result = formatter.format(long_text)

        # Should indicate continuation exists
        assert "..." in result or "more" in result.lower()

    def test_format_preserves_short_responses(self):
        """
        Test that short responses are preserved without truncation.
        """
        from src.voice_response import ResponseFormatter

        formatter = ResponseFormatter(max_words=100)

        short_text = "Lights turned on."
        result = formatter.format(short_text)

        assert result == short_text or result.rstrip('.') == short_text.rstrip('.')

    def test_format_normalizes_whitespace(self):
        """
        Test that format() normalizes excessive whitespace.
        """
        from src.voice_response import ResponseFormatter

        formatter = ResponseFormatter()

        messy_text = "Lights   turned    on.   Done."
        result = formatter.format(messy_text)

        assert "   " not in result  # No triple spaces
        assert result == "Lights turned on. Done." or "Lights turned on" in result


class TestResponseFormatterConfirmations:
    """Tests for confirmation message templates."""

    def test_confirmation_success(self):
        """
        Test success confirmation template.
        """
        from src.voice_response import ResponseFormatter

        formatter = ResponseFormatter()

        result = formatter.confirmation("lights", "turned on")

        assert "light" in result.lower()
        assert "on" in result.lower()
        # Should be concise
        assert len(result.split()) <= 10

    def test_confirmation_simple_done(self):
        """
        Test simple "Done" confirmation for single-action commands.
        """
        from src.voice_response import ResponseFormatter

        formatter = ResponseFormatter()

        result = formatter.confirmation_simple()

        assert result.lower() in ["done.", "done", "ok.", "ok", "okay."]
        assert len(result) <= 5

    def test_error_message_format(self):
        """
        Test error message formatting.

        Error messages should be:
        - Concise (for voice)
        - Not technical (no stack traces)
        - Actionable if possible
        """
        from src.voice_response import ResponseFormatter

        formatter = ResponseFormatter()

        # Technical error from agent
        technical_error = "ConnectionError: Failed to connect to http://192.168.1.100:8123"

        result = formatter.error(technical_error)

        # Should not contain technical details
        assert "ConnectionError" not in result
        assert "http://" not in result
        assert "192.168" not in result

        # Should be human-friendly
        assert "connect" in result.lower() or "error" in result.lower() or "sorry" in result.lower()

        # Should be short for voice
        assert len(result.split()) <= 20

    def test_error_timeout(self):
        """
        Test timeout error message.
        """
        from src.voice_response import ResponseFormatter

        formatter = ResponseFormatter()

        result = formatter.error_timeout()

        assert "time" in result.lower() or "slow" in result.lower() or "try again" in result.lower()
        assert len(result.split()) <= 15

    def test_error_not_understood(self):
        """
        Test "not understood" error message.
        """
        from src.voice_response import ResponseFormatter

        formatter = ResponseFormatter()

        result = formatter.error_not_understood()

        assert "understand" in result.lower() or "repeat" in result.lower() or "again" in result.lower()
        assert len(result.split()) <= 15


class TestResponseFormatterEdgeCases:
    """Tests for edge cases and special inputs."""

    def test_format_empty_string(self):
        """
        Test formatting empty string input.
        """
        from src.voice_response import ResponseFormatter

        formatter = ResponseFormatter()

        result = formatter.format("")

        # Should return empty or minimal response
        assert result == "" or result == "Done." or len(result) < 10

    def test_format_none_input(self):
        """
        Test formatting None input.
        """
        from src.voice_response import ResponseFormatter

        formatter = ResponseFormatter()

        result = formatter.format(None)

        # Should handle gracefully, not crash
        assert result is not None
        assert isinstance(result, str)

    def test_format_numeric_response(self):
        """
        Test formatting numeric responses (e.g., from time queries).
        """
        from src.voice_response import ResponseFormatter

        formatter = ResponseFormatter()

        result = formatter.format("The time is 2:30 PM")

        assert "2:30" in result or "two thirty" in result.lower()

    def test_format_list_response(self):
        """
        Test formatting list-style responses.

        Lists should be converted to speakable format.
        """
        from src.voice_response import ResponseFormatter

        formatter = ResponseFormatter()

        list_response = "Available rooms: 1. Living room 2. Bedroom 3. Kitchen"
        result = formatter.format(list_response)

        assert "living room" in result.lower()
        # Numbers should be speakable
        assert result  # Non-empty

    def test_format_multiline_response(self):
        """
        Test formatting multiline responses.

        Multiple lines should be joined for speech.
        """
        from src.voice_response import ResponseFormatter

        formatter = ResponseFormatter()

        multiline = "Line one.\nLine two.\nLine three."
        result = formatter.format(multiline)

        # Should be single line or properly joined for TTS
        # Newlines should be converted to spaces or punctuation pauses
        assert "\n" not in result or result.count("\n") == 0


class TestResponseFormatterCustomization:
    """Tests for formatter customization options."""

    def test_custom_max_words(self):
        """
        Test custom max words limit.
        """
        from src.voice_response import ResponseFormatter

        formatter = ResponseFormatter(max_words=5)

        long_text = "This is a very long response that should be truncated."
        result = formatter.format(long_text)

        assert len(result.split()) <= 6  # 5 + "..."

    def test_custom_chatty_phrases(self):
        """
        Test adding custom chatty phrases to filter.
        """
        from src.voice_response import ResponseFormatter

        custom_phrases = ["You bet!", "For sure!"]
        formatter = ResponseFormatter(extra_chatty_phrases=custom_phrases)

        result = formatter.format("You bet! The lights are on.")

        assert not result.lower().startswith("you bet")

    def test_preserve_numbers_and_units(self):
        """
        Test that numbers and units are preserved.

        Important for temperature, time, percentages.
        """
        from src.voice_response import ResponseFormatter

        formatter = ResponseFormatter()

        responses = [
            "Temperature is 72 degrees Fahrenheit",
            "Brightness set to 50 percent",
            "Timer set for 10 minutes",
        ]

        for response in responses:
            result = formatter.format(response)
            # Numbers should be preserved
            assert any(char.isdigit() for char in result)
