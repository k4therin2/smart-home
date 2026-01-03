# UI Tests - Feedback Feature

Browser-based UI tests for the response feedback feature using Playwright.

## Overview

This test suite validates the feedback UI components that allow users to provide feedback on assistant responses. The tests cover the complete user flow from clicking feedback buttons to submitting additional context.

## Test Coverage

### 1. Feedback Button Rendering (`TestFeedbackButtonRendering`)
- ✅ Buttons appear with responses
- ✅ Buttons have correct ARIA attributes
- ✅ Multiple responses each get feedback buttons
- ✅ Touch-friendly sizing (44px minimum)

### 2. Thumbs Up Flow (`TestThumbsUpFlow`)
- ✅ Shows "Thanks for the feedback!" confirmation
- ✅ Hides both feedback buttons after click
- ✅ SVG icon renders correctly

### 3. Thumbs Down Flow (`TestThumbsDownFlow`)
- ✅ Shows "Filing bug..." loading state
- ✅ Shows bug ID after successful filing
- ✅ Shows "..." button for additional context
- ✅ Hides down button after click
- ✅ Shows error message on API failure

### 4. Feedback Form (`TestFeedbackForm`)
- ✅ "..." button expands feedback form
- ✅ Form has input field and submit/cancel buttons
- ✅ Input field receives focus on form open
- ✅ Cancel button hides form
- ✅ Submit with text triggers retry flow
- ✅ Submit empty text just closes form
- ✅ Retry failure shows error message

### 5. Visual Regression (`TestFeedbackVisuals`)
- ✅ Buttons have correct styling
- ✅ Form has proper background and spacing
- ✅ Success message uses success color

### 6. Accessibility (`TestFeedbackAccessibility`)
- ✅ Buttons have ARIA labels
- ✅ Input has ARIA label
- ✅ SVG icons marked `aria-hidden="true"`

### 7. End-to-End (`TestFeedbackEndToEnd`)
- ✅ Complete flow from thumbs down to retry with context

## Prerequisites

### 1. Install Playwright

```bash
# Activate virtual environment
source venv/bin/activate

# Install playwright
pip install playwright

# Install browser drivers
playwright install
```

### 2. Start the Server

The tests require the Smarthome web server to be running:

```bash
# In a separate terminal
source venv/bin/activate
python server.py
```

By default, tests expect the server at `http://localhost:5050`. You can override this:

```bash
export TEST_URL=http://localhost:5000
```

## Running the Tests

### Run all UI tests

```bash
source venv/bin/activate
pytest tests/ui/ -v
```

### Run only feedback tests

```bash
pytest tests/ui/test_feedback_ui.py -v
```

### Run specific test class

```bash
pytest tests/ui/test_feedback_ui.py::TestThumbsUpFlow -v
```

### Run specific test

```bash
pytest tests/ui/test_feedback_ui.py::TestThumbsUpFlow::test_thumbs_up_shows_success_message -v
```

### Run with browser visible (non-headless)

Edit the test file and change:

```python
browser = playwright.chromium.launch(headless=True)
```

to:

```python
browser = playwright.chromium.launch(headless=False)
```

## Screenshots

Tests automatically capture screenshots at key points in the flow. Screenshots are saved to:

```
tests/screenshots/feedback/
```

### Screenshot Index

1. `01_buttons_rendered.png` - Feedback buttons visible
2. `02_multiple_responses.png` - Multiple responses with buttons
3. `03_thumbs_up_success.png` - Success message after thumbs up
4. `04_thumbs_down_loading.png` - Loading state during bug filing
5. `05_bug_filed_success.png` - Bug filed confirmation
6. `06_api_error.png` - Error message display
7. `07_form_expanded.png` - Feedback form expanded
8. `08_form_cancelled.png` - Form after cancel
9. `09_retry_success.png` - Successful retry result
10. `10_retry_failure.png` - Retry failure error
11. `e2e_*.png` - End-to-end flow screenshots

## Test Architecture

### Mock Response Injection

Tests use `inject_mock_response()` to bypass actual API calls and directly inject responses:

```python
inject_mock_response(page, "turn on kitchen light", "Done!")
```

This allows testing UI behavior without requiring:
- Full server implementation
- Live Home Assistant instance
- OpenAI API calls

### API Mocking

Tests mock the `/api/feedback` endpoint using Playwright's route interception:

```python
page.route("**/api/feedback", lambda route: route.fulfill(
    status=200,
    body='{"success": true, "action": "bug_filed", "bug_id": "BUG-123"}',
    headers={"Content-Type": "application/json"}
))
```

This allows testing:
- Success flows
- Error handling
- Network failures
- Specific response payloads

## Debugging Tests

### View browser during test

Change `headless=True` to `headless=False` in test methods.

### Add pauses for inspection

```python
page.pause()  # Opens Playwright Inspector
```

### Check element visibility

```python
element = page.locator(".feedback-btn-up")
print(f"Visible: {element.is_visible()}")
print(f"Count: {page.locator('.feedback-btn-up').count()}")
```

### View console logs

```python
page.on("console", lambda msg: print(f"Console: {msg.text}"))
```

## Common Issues

### Test fails with "playwright not installed"

```bash
pip install playwright
playwright install
```

### Test fails with "connection refused"

Ensure server is running:

```bash
python server.py
```

### Element not found errors

Increase timeout:

```python
page.wait_for_selector(".feedback-btn-up", timeout=5000)  # 5 seconds
```

### Screenshots show unexpected state

Check timing - add `page.wait_for_timeout(ms)` before screenshot.

## Contributing

When adding new feedback UI features:

1. Add corresponding UI tests to this file
2. Update test coverage section in this README
3. Capture screenshots of new flows
4. Ensure accessibility tests cover new elements

## Integration with CI/CD

These tests can run in CI with headless browsers:

```yaml
# .github/workflows/test.yml
- name: Install Playwright
  run: |
    pip install playwright
    playwright install --with-deps chromium

- name: Run UI Tests
  run: |
    pytest tests/ui/ -v --screenshot=on-failure
```

## Related Documentation

- [Feedback Feature Unit Tests](../unit/test_feedback.py)
- [Feedback API Tests](../api/test_feedback_api.py)
- [Feedback Handler Implementation](../../src/feedback_handler.py)
- [Static JS Implementation](../../static/app.js) (lines 179-334)
- [CSS Styles](../../static/style.css) (lines 1067-1230)
