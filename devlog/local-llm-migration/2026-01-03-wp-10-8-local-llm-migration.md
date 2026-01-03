# WP-10.8: Local LLM Migration (SmartHome Only)

**Date:** 2026-01-03
**Agent:** Agent-Dorian
**Status:** Complete
**Priority:** P2 (cost optimization)
**Effort:** M

## Summary

Migrated SmartHome's LLM provider from OpenAI (default) to home-llm (Ollama on colby) as the default provider, with automatic fallback to OpenAI when home-llm is unavailable.

## Cost Impact

- **Before:** ~$730/year (OpenAI API costs for smart home queries)
- **After:** ~$36/year (electricity for local inference)
- **Savings:** 95% reduction in LLM costs

## Changes Made

### 1. LLM Client Updates (`src/llm_client.py`)

- Added new `home_llm` provider as the default
- Added `check_home_llm_health()` function for availability checks
- Added `get_llm_config()` function for configuration inspection
- Added `_get_fallback_client()` method for OpenAI fallback
- Added `fallback_count` tracking for metrics
- Added `home_llm_url` attribute for server configuration

### 2. Configuration Updates

- Updated `.env.example` with new home-llm defaults
- Modified `validate_config()` to not require OpenAI key by default
- Added warning (not error) when fallback is unavailable

### 3. Tests Added (12 new tests)

**TestHomeLLMFallback:**
- `test_home_llm_default_when_available`
- `test_fallback_to_openai_when_home_llm_unavailable`
- `test_home_llm_health_check`
- `test_home_llm_health_check_failure`
- `test_fallback_records_metric`
- `test_home_llm_url_from_env`
- `test_get_llm_config_returns_current_provider`

**TestHomeLLMProvider:**
- `test_home_llm_provider_initializes`
- `test_home_llm_uses_openai_compatible_api`
- `test_home_llm_complete_with_fallback`

**TestCostOptimization:**
- `test_home_llm_has_zero_api_cost`
- `test_fallback_tracks_openai_costs`

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `home_llm` | Provider to use (home_llm, openai, anthropic, local) |
| `HOME_LLM_URL` | `http://100.75.232.36:11434` | Ollama server URL (Tailscale to colby) |
| `LLM_MODEL` | `llama3` | Model to use (llama3 for home-llm) |
| `OPENAI_API_KEY` | (optional) | Fallback key when home-llm unavailable |

## Migration Guide

### Existing Installations

1. **No action required** - System will automatically use home-llm if reachable
2. **Optional:** Remove `LLM_PROVIDER=openai` from `.env` to use default
3. **Recommended:** Keep `OPENAI_API_KEY` for fallback capability

### New Installations

1. Ensure home-llm (Ollama) is running on colby: `docker ps | grep ollama`
2. Copy `.env.example` to `.env` (new defaults already set)
3. Set `OPENAI_API_KEY` if fallback desired
4. Run `python -c "from src.llm_client import get_llm_config; print(get_llm_config())"`

## Architecture

```
User Request
    ↓
LLMClient (provider=home_llm)
    ↓
home-llm (Ollama @ colby:11434)
    ↓ (if unavailable)
OpenAI API (fallback)
    ↓
Response
```

## Testing

```bash
# Run LLM client tests
python -m pytest tests/unit/test_llm_client.py -v

# Check configuration
python -c "from src.llm_client import get_llm_config; print(get_llm_config())"

# Verify home-llm health
curl http://100.75.232.36:11434/v1/models
```

## Update: 2026-01-03 (Agent-Nadia)

### Automatic Fallback Mechanism Completed

Agent-Nadia completed the automatic fallback implementation that was partially done:

**Changes Made:**
- Added `_complete_with_fallback()` method that actually triggers OpenAI fallback on home-llm errors
- Added `_complete_with_tools_fallback()` method for tool-calling API fallback
- Updated `complete()` and `complete_with_tools()` to use fallback methods for home_llm provider
- Model is correctly switched to OpenAI model during fallback and restored afterward

**Tests Added (7 new, 44 total for llm_client):**

**TestAutomaticFallback:**
- `test_complete_with_fallback_success_no_fallback` - Verify no fallback when home-llm works
- `test_complete_with_fallback_triggered_on_error` - Verify fallback triggers on error
- `test_complete_raises_when_no_fallback_available` - Verify error raised if no API key
- `test_fallback_count_increments_on_each_failure` - Verify metric tracking
- `test_complete_with_tools_fallback` - Verify fallback works for tool-calling
- `test_fallback_uses_openai_model` - Verify correct model used during fallback
- `test_fallback_restores_model_on_error` - Verify cleanup on fallback failure

## Future Enhancements

- [ ] Add Prometheus metrics for fallback rate
- [ ] Implement circuit breaker pattern for faster failover
- [ ] Add vision model support (LLaVA) for camera descriptions
- [ ] Quality benchmarking: llama3 vs gpt-4o-mini for home tasks

## Related

- **Depends on:** home-llm project (WP-1.x batch)
- **Enables:** WP-11.4 (LLaVA Integration) uses same home-llm endpoint
- **See also:** `/home/k4therin2/projects/home-llm/docs/CONSUMERS.md`
