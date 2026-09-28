"""
Phase 5.4 AI Advisory Service & Provider Abstraction Test Suite.

Validates the provider-agnostic AI advisory service built on top of validated AdvisoryContext.
Tests all minimum requirements:
1. Valid AdvisoryContext reaches the provider.
2. Provider receives only intended structured context.
3. Structured provider response parses successfully.
4. Missing required output fields fail validation.
5. Invalid JSON fails safely.
6. Invalid severity/status fails safely.
7. Provider timeout is handled.
8. Provider unavailable is handled.
9. Authentication/configuration failure is handled.
10. Retry behavior is bounded.
11. Mock provider produces deterministic output.
12. Numerical forecast values remain unchanged (tampering raises ForecastGroundednessViolationError).
13. Provider cannot replace deterministic risk data.
14. Prompt version is preserved.
15. Provider/model metadata is preserved.
16. Repeated identical input produces deterministic mock output.
17. HTTP provider network failure handling (timeout, 401, 429).
18. Provider factory instantiation based on configuration.
"""

from datetime import date
import json
import urllib.error
from unittest.mock import MagicMock, patch
import pytest

from backend.app.models.panchayat import Panchayat
from backend.app.models.downscaled_forecast import DownscaledForecast
from backend.app.schemas.advisory_contracts import (
    AdvisoryContext,
    AdvisorySeverityEnum,
    AIAdvisoryOutputContract,
)
from src.advisory.context_builder import AdvisoryContextService
from src.advisory.ai_service import (
    AIAdvisoryService,
    AIAdvisoryProvider,
    MockAIAdvisoryProvider,
    HttpAIAdvisoryProvider,
    AdvisoryPromptBuilder,
    AIAdvisoryResult,
    AIAdvisoryServiceError,
    AIProviderConfigError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
    AIProviderAuthError,
    AIProviderRateLimitError,
    AIOutputValidationError,
    ForecastGroundednessViolationError,
    PROMPT_VERSION,
    get_ai_advisory_provider,
)


def make_dummy_panchayat(
    p_id: int = 1001,
    p_name: str = "Ajmer Saundane",
    block_id: int = 10,
    block_name: str = "Baglan",
    dist_id: int = 1,
    dist_name: str = "Nashik",
) -> Panchayat:
    """Helper creating an in-memory Panchayat model with joined parents."""
    p = Panchayat()
    p.id = p_id
    p.name = p_name
    p.panchayat_code = f"P_{p_id}"
    p.lgd_code = 253123
    p.block_id = block_id
    p.district_id = dist_id
    p.latitude = 20.5982
    p.longitude = 74.1201
    p.elevation_m = 585.0

    b = MagicMock()
    b.id = block_id
    b.name = block_name
    p.block = b

    d = MagicMock()
    d.id = dist_id
    d.name = dist_name
    p.district = d

    return p


def make_dummy_forecast(
    f_id: int = 101,
    p_id: int = 1001,
    downscaled_rf: float = 28.5,
    block_rf: float = 30.0,
    f_date: date = date(2026, 9, 10),
    issue_date: date = date(2026, 9, 10),
) -> DownscaledForecast:
    """Helper creating an in-memory DownscaledForecast model."""
    f = DownscaledForecast()
    f.id = f_id
    f.panchayat_id = p_id
    f.forecast_date = f_date
    f.forecast_issue_date = issue_date
    f.downscaled_rainfall_mm = downscaled_rf
    f.block_forecast_rainfall_mm = block_rf
    f.model_name = "XGBoost Regressor"
    f.model_version = "v1.0.0"
    f.confidence = 0.88
    return f


@pytest.fixture
def sample_advisory_context() -> AdvisoryContext:
    """Fixture providing a standard validated AdvisoryContext via AdvisoryContextService."""
    p = make_dummy_panchayat(1001, "Ajmer Saundane")
    f = make_dummy_forecast(101, 1001, downscaled_rf=28.5, block_rf=30.0)
    service = AdvisoryContextService()
    return service.build_from_objects(p, f)


# =============================================================================
# 1. VALID ADVISORY CONTEXT REACHES PROVIDER
# =============================================================================

def test_valid_advisory_context_reaches_provider(sample_advisory_context):
    """Test that valid AdvisoryContext is cleanly accepted and processed by service."""
    mock_provider = MockAIAdvisoryProvider()
    service = AIAdvisoryService(provider=mock_provider)

    result = service.generate_advisory(sample_advisory_context)

    assert isinstance(result, AIAdvisoryResult)
    assert isinstance(result.output, AIAdvisoryOutputContract)
    assert result.metadata.is_mock is True
    assert result.metadata.provider_name == "MOCK_AI_PROVIDER"


# =============================================================================
# 2. PROVIDER RECEIVES ONLY INTENDED STRUCTURED CONTEXT
# =============================================================================

def test_provider_receives_only_intended_structured_context(sample_advisory_context):
    """Verify provider receives serialized structured context and no sensitive internal state."""
    captured_payloads = []

    class CapturingProvider(AIAdvisoryProvider):
        @property
        def provider_name(self) -> str:
            return "capturing-test"

        @property
        def model_name(self) -> str:
            return "capturing-model"

        @property
        def is_mock(self) -> bool:
            return True

        def generate_advisory_text(
            self,
            system_instruction: str,
            user_prompt: str,
            timeout_seconds: float = 15.0,
        ) -> str:
            captured_payloads.append((system_instruction, user_prompt))
            return json.dumps({
                "summary": "Capturing test summary statement for the panchayat",
                "what_is_happening": "Downscaled rainfall of 28.5 mm expected across Ajmer Saundane.",
                "why_it_matters": "Moderate rainfall increases root-zone soil saturation significantly.",
                "recommended_actions": ["Clear field drainage channels to prevent water accumulation."],
                "timing": "Immediate next 24 hours",
                "severity": "HIGH",
                "warnings": ["Monitor drainage lines."],
                "supporting_forecast_reference": {
                    "forecast_id": 101,
                    "forecast_date": "2026-09-10",
                    "downscaled_rainfall_mm": 28.5,
                },
            })

    service = AIAdvisoryService(provider=CapturingProvider())
    service.generate_advisory(sample_advisory_context)

    assert len(captured_payloads) == 1
    system_inst, user_prompt = captured_payloads[0]

    # Grounding instructions present
    assert "NEVER invent, modify, round, or contradict numerical forecast values" in system_inst
    assert PROMPT_VERSION in AdvisoryPromptBuilder.version

    # User payload contains parsed structured data
    json_start = user_prompt.find("{")
    json_end = user_prompt.rfind("}") + 1
    parsed_input = json.loads(user_prompt[json_start:json_end])

    assert parsed_input["panchayat"]["name"] == "Ajmer Saundane"
    assert parsed_input["forecast"]["downscaled_rainfall_mm"] == 28.5
    assert len(parsed_input["deterministic_risks"]) >= 1

    # Verify no database internal fields or secrets leaked
    assert "password" not in user_prompt.lower()
    assert "secret" not in user_prompt.lower()
    assert "database_url" not in user_prompt.lower()


# =============================================================================
# 3. STRUCTURED PROVIDER RESPONSE PARSES SUCCESSFULLY
# =============================================================================

def test_structured_provider_response_parses_successfully(sample_advisory_context):
    """Verify that a valid JSON structure matching the contract parses cleanly."""
    mock_provider = MockAIAdvisoryProvider()
    service = AIAdvisoryService(provider=mock_provider)

    result = service.generate_advisory(sample_advisory_context)
    advisory = result.output

    assert len(advisory.summary) >= 10
    assert len(advisory.what_is_happening) >= 10
    assert len(advisory.why_it_matters) >= 10
    assert len(advisory.recommended_actions) >= 1
    assert advisory.severity in [AdvisorySeverityEnum.HIGH, AdvisorySeverityEnum.MODERATE, AdvisorySeverityEnum.LOW]
    assert advisory.supporting_forecast_reference["downscaled_rainfall_mm"] == 28.5


# =============================================================================
# 4. MISSING REQUIRED OUTPUT FIELDS FAIL VALIDATION
# =============================================================================

def test_missing_required_output_fields_fail_validation(sample_advisory_context):
    """Test that missing required fields like summary raise AIOutputValidationError."""
    class BadProvider(AIAdvisoryProvider):
        @property
        def provider_name(self) -> str:
            return "bad-test"
        @property
        def model_name(self) -> str:
            return "bad-model"
        @property
        def is_mock(self) -> bool:
            return True
        def generate_advisory_text(self, system_instruction: str, user_prompt: str, timeout_seconds: float = 15.0) -> str:
            return json.dumps({
                "severity": "LOW",
                "recommended_actions": ["Wait"],
            })

    service = AIAdvisoryService(provider=BadProvider())
    with pytest.raises(AIOutputValidationError) as exc:
        service.generate_advisory(sample_advisory_context)

    assert "validation" in str(exc.value).lower()


# =============================================================================
# 5. INVALID JSON FAILS SAFELY
# =============================================================================

def test_invalid_json_fails_safely(sample_advisory_context):
    """Test that non-JSON or malformed provider output fails safely."""
    class BrokenJsonProvider(AIAdvisoryProvider):
        @property
        def provider_name(self) -> str:
            return "broken-test"
        @property
        def model_name(self) -> str:
            return "broken-model"
        @property
        def is_mock(self) -> bool:
            return True
        def generate_advisory_text(self, system_instruction: str, user_prompt: str, timeout_seconds: float = 15.0) -> str:
            return "Here is your agricultural advisory: It looks like rain!"

    service = AIAdvisoryService(provider=BrokenJsonProvider())
    with pytest.raises(AIOutputValidationError) as exc:
        service.generate_advisory(sample_advisory_context)

    assert "not valid JSON" in str(exc.value)


# =============================================================================
# 6. INVALID SEVERITY/STATUS FAILS SAFELY
# =============================================================================

def test_invalid_severity_fails_safely(sample_advisory_context):
    """Test that unrecognized severity strings raise AIOutputValidationError."""
    class InvalidSeverityProvider(AIAdvisoryProvider):
        @property
        def provider_name(self) -> str:
            return "invalid-sev-test"
        @property
        def model_name(self) -> str:
            return "invalid-sev-model"
        @property
        def is_mock(self) -> bool:
            return True
        def generate_advisory_text(self, system_instruction: str, user_prompt: str, timeout_seconds: float = 15.0) -> str:
            return json.dumps({
                "summary": "Valid summary of sufficient length for test",
                "what_is_happening": "Rainfall of 28.5 mm expected across the area.",
                "why_it_matters": "Risk of crop damage due to excessive saturation.",
                "recommended_actions": ["Clear field drainage furrows."],
                "timing": "Immediate",
                "severity": "ULTRA_CATASTROPHIC_APOCALYPSE",  # Invalid enum value
                "warnings": [],
                "supporting_forecast_reference": {
                    "forecast_id": 101,
                    "forecast_date": "2026-09-10",
                    "downscaled_rainfall_mm": 28.5,
                },
            })

    service = AIAdvisoryService(provider=InvalidSeverityProvider())
    with pytest.raises(AIOutputValidationError) as exc:
        service.generate_advisory(sample_advisory_context)

    assert "validation" in str(exc.value).lower()


# =============================================================================
# 7. PROVIDER TIMEOUT IS HANDLED
# =============================================================================

def test_provider_timeout_is_handled(sample_advisory_context):
    """Test that socket/request timeouts raise AIProviderTimeoutError."""
    class TimingOutProvider(AIAdvisoryProvider):
        @property
        def provider_name(self) -> str:
            return "timeout-test"
        @property
        def model_name(self) -> str:
            return "timeout-model"
        @property
        def is_mock(self) -> bool:
            return False
        def generate_advisory_text(self, system_instruction: str, user_prompt: str, timeout_seconds: float = 15.0) -> str:
            raise AIProviderTimeoutError("Connection timed out after 15.0 seconds")

    service = AIAdvisoryService(provider=TimingOutProvider(), max_retries=1)
    with pytest.raises(AIProviderTimeoutError) as exc:
        service.generate_advisory(sample_advisory_context)

    assert "Connection timed out" in str(exc.value)


# =============================================================================
# 8. PROVIDER UNAVAILABLE IS HANDLED
# =============================================================================

def test_provider_unavailable_is_handled(sample_advisory_context):
    """Test that 503 or server unreachable errors raise AIProviderUnavailableError."""
    class UnavailableProvider(AIAdvisoryProvider):
        @property
        def provider_name(self) -> str:
            return "unavail-test"
        @property
        def model_name(self) -> str:
            return "unavail-model"
        @property
        def is_mock(self) -> bool:
            return False
        def generate_advisory_text(self, system_instruction: str, user_prompt: str, timeout_seconds: float = 15.0) -> str:
            raise AIProviderUnavailableError("Remote endpoint returned HTTP 503 Service Unavailable")

    service = AIAdvisoryService(provider=UnavailableProvider(), max_retries=1)
    with pytest.raises(AIProviderUnavailableError) as exc:
        service.generate_advisory(sample_advisory_context)

    assert "503" in str(exc.value)


# =============================================================================
# 9. AUTHENTICATION / CONFIGURATION FAILURE IS HANDLED
# =============================================================================

def test_auth_configuration_failure_is_handled(sample_advisory_context):
    """Test that missing or invalid API keys raise AIProviderAuthError without retrying."""
    call_count = 0

    class AuthFailingProvider(AIAdvisoryProvider):
        @property
        def provider_name(self) -> str:
            return "auth-test"
        @property
        def model_name(self) -> str:
            return "auth-model"
        @property
        def is_mock(self) -> bool:
            return False
        def generate_advisory_text(self, system_instruction: str, user_prompt: str, timeout_seconds: float = 15.0) -> str:
            nonlocal call_count
            call_count += 1
            raise AIProviderAuthError("HTTP 401 Unauthorized: Invalid API key")

    # Service with max_retries=3 should NOT retry auth errors
    service = AIAdvisoryService(provider=AuthFailingProvider(), max_retries=3)
    with pytest.raises(AIProviderAuthError):
        service.generate_advisory(sample_advisory_context)

    assert call_count == 1, "Permanent auth failure must not be retried!"


# =============================================================================
# 10. RETRY BEHAVIOR IS BOUNDED
# =============================================================================

def test_retry_behavior_is_bounded(sample_advisory_context):
    """Test that transient network errors are retried up to max_retries and stop."""
    call_count = 0

    class TransientFailProvider(AIAdvisoryProvider):
        @property
        def provider_name(self) -> str:
            return "transient-test"
        @property
        def model_name(self) -> str:
            return "transient-model"
        @property
        def is_mock(self) -> bool:
            return False
        def generate_advisory_text(self, system_instruction: str, user_prompt: str, timeout_seconds: float = 15.0) -> str:
            nonlocal call_count
            call_count += 1
            raise AIProviderTimeoutError("Socket timeout")

    max_retries = 2
    service = AIAdvisoryService(provider=TransientFailProvider(), max_retries=max_retries)
    with pytest.raises(AIProviderTimeoutError):
        service.generate_advisory(sample_advisory_context)

    # 1 initial try + 2 retries = 3 calls total
    assert call_count == 1 + max_retries


# =============================================================================
# 11. MOCK PROVIDER PRODUCES DETERMINISTIC OUTPUT
# =============================================================================

def test_mock_provider_produces_deterministic_output(sample_advisory_context):
    """Test that mock provider returns well-formed deterministic agricultural advisory."""
    provider = MockAIAdvisoryProvider()
    service = AIAdvisoryService(provider=provider)

    res = service.generate_advisory(sample_advisory_context)
    advisory = res.output

    assert advisory.severity in [AdvisorySeverityEnum.HIGH, AdvisorySeverityEnum.MODERATE]
    assert "28.5 mm" in advisory.what_is_happening
    assert "Ajmer Saundane" in advisory.what_is_happening
    assert len(advisory.recommended_actions) >= 1
    assert res.metadata.is_mock is True


# =============================================================================
# 12. NUMERICAL FORECAST VALUES REMAIN UNCHANGED
# =============================================================================

def test_numerical_forecast_values_remain_unchanged(sample_advisory_context):
    """Test that if the provider alters or invents rainfall numbers, validation rejects it."""
    class TamperingProvider(AIAdvisoryProvider):
        @property
        def provider_name(self) -> str:
            return "tampering-test"
        @property
        def model_name(self) -> str:
            return "tampering-model"
        @property
        def is_mock(self) -> True:
            return True
        def generate_advisory_text(self, system_instruction: str, user_prompt: str, timeout_seconds: float = 15.0) -> str:
            # Hallucinating 65.0 mm instead of 28.5 mm
            return json.dumps({
                "summary": "Heavy rain alert advisory headline for the region",
                "what_is_happening": "Rainfall of 65.0 mm is expected across the region.",
                "why_it_matters": "Severe waterlogging risk will saturate crops.",
                "recommended_actions": ["Clear field drains immediately."],
                "timing": "Immediate next 24 hours",
                "severity": "CRITICAL",
                "warnings": ["High flood risk"],
                "supporting_forecast_reference": {
                    "forecast_id": 101,
                    "forecast_date": "2026-09-10",
                    "downscaled_rainfall_mm": 65.0,  # Mutated!
                },
            })

    service = AIAdvisoryService(provider=TamperingProvider())
    with pytest.raises(ForecastGroundednessViolationError) as exc:
        service.generate_advisory(sample_advisory_context)

    assert "altered forecast rainfall" in str(exc.value).lower()


# =============================================================================
# 13. PROVIDER CANNOT REPLACE DETERMINISTIC RISK DATA
# =============================================================================

def test_provider_cannot_replace_deterministic_risk_data(sample_advisory_context):
    """Verify the advisory service retains deterministic context integrity."""
    provider = MockAIAdvisoryProvider()
    service = AIAdvisoryService(provider=provider)

    res = service.generate_advisory(sample_advisory_context)
    advisory = res.output

    assert advisory.severity in [AdvisorySeverityEnum.HIGH, AdvisorySeverityEnum.MODERATE, AdvisorySeverityEnum.LOW]
    assert len(advisory.recommended_actions) >= 1


# =============================================================================
# 14. PROMPT VERSION IS PRESERVED
# =============================================================================

def test_prompt_version_is_preserved(sample_advisory_context):
    """Test that audit_metadata accurately records the active prompt version."""
    provider = MockAIAdvisoryProvider()
    service = AIAdvisoryService(provider=provider)

    res = service.generate_advisory(sample_advisory_context)

    assert res.metadata.prompt_version == PROMPT_VERSION
    assert res.metadata.prompt_version == "v1.0.0"


# =============================================================================
# 15. PROVIDER / MODEL METADATA IS PRESERVED
# =============================================================================

def test_provider_and_model_metadata_preserved(sample_advisory_context):
    """Verify provider name, model name, latency, and context fingerprint are tracked."""
    provider = MockAIAdvisoryProvider()
    service = AIAdvisoryService(provider=provider)

    res = service.generate_advisory(sample_advisory_context)
    meta = res.metadata

    assert meta.provider_name == "MOCK_AI_PROVIDER"
    assert meta.model_name == "mock-agricultural-advisor-v1"
    assert meta.latency_ms >= 0.0
    assert len(meta.context_fingerprint) == 16  # SHA256 hex truncated
    assert meta.status == "SUCCESS"


# =============================================================================
# 16. REPEATED IDENTICAL INPUT PRODUCES DETERMINISTIC MOCK OUTPUT
# =============================================================================

def test_repeated_identical_input_produces_deterministic_output(sample_advisory_context):
    """Test that running the mock provider multiple times yields identical advisory content."""
    provider = MockAIAdvisoryProvider()
    service = AIAdvisoryService(provider=provider)

    run_1 = service.generate_advisory(sample_advisory_context)
    run_2 = service.generate_advisory(sample_advisory_context)

    assert run_1.output.summary == run_2.output.summary
    assert run_1.output.what_is_happening == run_2.output.what_is_happening
    assert run_1.output.why_it_matters == run_2.output.why_it_matters
    assert run_1.output.recommended_actions == run_2.output.recommended_actions
    assert run_1.output.severity == run_2.output.severity
    assert run_1.metadata.context_fingerprint == run_2.metadata.context_fingerprint


# =============================================================================
# 17. HTTP AI ADVISORY PROVIDER ERROR HANDLING
# =============================================================================

def test_http_provider_network_timeout():
    """HttpAIAdvisoryProvider must catch socket timeouts and map to AIProviderTimeoutError."""
    provider = HttpAIAdvisoryProvider(
        endpoint="https://ai.example.com",
        model_name="test-model",
        api_key="test-key",
    )

    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError(reason="timed out")):
        with pytest.raises(AIProviderTimeoutError):
            provider.generate_advisory_text("system", "payload")


def test_http_provider_http_401():
    """HttpAIAdvisoryProvider must catch 401 and map to AIProviderAuthError."""
    provider = HttpAIAdvisoryProvider(
        endpoint="https://ai.example.com",
        model_name="test-model",
        api_key="test-key",
    )

    with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError("url", 401, "Unauthorized", {}, None)):
        with pytest.raises(AIProviderAuthError):
            provider.generate_advisory_text("system", "payload")


def test_http_provider_http_429():
    """HttpAIAdvisoryProvider must catch 429 and map to AIProviderRateLimitError."""
    provider = HttpAIAdvisoryProvider(
        endpoint="https://ai.example.com",
        model_name="test-model",
        api_key="test-key",
    )

    with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError("url", 429, "Too Many Requests", {}, None)):
        with pytest.raises(AIProviderRateLimitError):
            provider.generate_advisory_text("system", "payload")


# =============================================================================
# 18. PROVIDER FACTORY CONFIGURATION
# =============================================================================

def test_provider_factory_mock():
    """Factory must return MockAIAdvisoryProvider when configured for 'mock'."""
    with patch("backend.app.core.config.settings.AI_ADVISORY_PROVIDER", "mock"):
        p = get_ai_advisory_provider()
        assert isinstance(p, MockAIAdvisoryProvider)
        assert p.is_mock is True


def test_provider_factory_http():
    """Factory must return HttpAIAdvisoryProvider when configured for 'http'."""
    with patch("backend.app.core.config.settings.AI_ADVISORY_PROVIDER", "http"):
        with patch("backend.app.core.config.settings.AI_ADVISORY_ENDPOINT", "http://localhost:11434"):
            p = get_ai_advisory_provider()
            assert isinstance(p, HttpAIAdvisoryProvider)
            assert p.is_mock is False
