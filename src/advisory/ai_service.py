"""
Phase 5.4 AI Advisory Service & Provider Abstraction.

Implements a provider-agnostic AI advisory generation layer on top of the
validated AdvisoryContext created in Phase 5.3:
  Validated Forecast Context + Deterministic Rules + Authoritative Panchayat Metadata
  -> AdvisoryContext
  -> AI Advisory Service
  -> Provider Adapter (Mock / HTTP Ollama / Cloud LLM)
  -> Structured AI Advisory Output (AIAdvisoryOutputContract)
  -> Future Phase 5.5 Safety Validation & Officer Review

Safety & Architectural Invariants:
1. Zero Weather Invention: AI never predicts, modifies, rounds, or overwrites numerical weather values.
2. Rule Grounding: AI explains and articulates the deterministic rule results; it never overrides them.
3. Provider Neutrality: Complete decoupling from specific vendor SDKs via AIAdvisoryProvider abstraction.
4. Deterministic Development Mode: MockAIAdvisoryProvider guarantees reproducible test and local execution.
5. Strict Schema Validation: All output must conform to AIAdvisoryOutputContract; free-form text is rejected.
6. Zero Farmer Release: AI generation produces drafts only; officer approval is mandatory.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
import math
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import urllib.request
import urllib.error

from backend.app.core.config import settings
from backend.app.schemas.advisory_contracts import (
    AdvisoryContext,
    AIAdvisoryInputContract,
    AIAdvisoryOutputContract,
    AdvisorySeverityEnum,
    PanchayatContext,
    ForecastContext,
)

logger = logging.getLogger(__name__)

PROMPT_VERSION = "v1.0.0"


# =============================================================================
# 1. STRUCTURED ERROR TAXONOMY
# =============================================================================

class AIAdvisoryServiceError(Exception):
    """Base exception for AI advisory service errors."""
    def __init__(
        self,
        message: str,
        code: str = "AI_SERVICE_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class AIProviderConfigError(AIAdvisoryServiceError):
    """Raised when provider configuration or credentials are missing/invalid."""
    def __init__(self, message: str):
        super().__init__(message, code="CONFIG_ERROR")


class AIProviderTimeoutError(AIAdvisoryServiceError):
    """Raised when the AI provider times out during generation."""
    def __init__(self, message: str):
        super().__init__(message, code="TIMEOUT_ERROR")


class AIProviderUnavailableError(AIAdvisoryServiceError):
    """Raised when the AI provider cannot be reached (HTTP 502/503/504 / network fault)."""
    def __init__(self, message: str):
        super().__init__(message, code="UNAVAILABLE_ERROR")


class AIProviderAuthError(AIAdvisoryServiceError):
    """Raised when authentication with the AI provider fails (HTTP 401/403)."""
    def __init__(self, message: str):
        super().__init__(message, code="AUTH_ERROR")


class AIProviderRateLimitError(AIAdvisoryServiceError):
    """Raised when the AI provider quota or rate limit is exceeded (HTTP 429)."""
    def __init__(self, message: str):
        super().__init__(message, code="RATE_LIMIT_ERROR")


class AIOutputValidationError(AIAdvisoryServiceError):
    """Raised when AI response fails JSON parsing, schema validation, or required fields."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="VALIDATION_ERROR", details=details)


class ForecastGroundednessViolationError(AIAdvisoryServiceError):
    """Raised when AI advisory contradicts or alters the numerical forecast values."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="GROUNDEDNESS_ERROR", details=details)


# =============================================================================
# 2. OBSERVABILITY & EXECUTION METADATA
# =============================================================================

@dataclass
class AIExecutionMetadata:
    """Audit metadata tracking the AI generation call without exposing secrets."""
    provider_name: str
    model_name: str
    prompt_version: str
    latency_ms: float
    status: str
    timestamp: str
    is_mock: bool
    retries_taken: int
    context_fingerprint: str


@dataclass
class AIAdvisoryResult:
    """Complete generation outcome combining validated output and audit metadata."""
    output: AIAdvisoryOutputContract
    metadata: AIExecutionMetadata


# =============================================================================
# 3. PROMPT BUILDER
# =============================================================================

class AdvisoryPromptBuilder:
    """
    Constructs versioned, safety-constrained system instructions and user payloads
    from validated AIAdvisoryInputContract instances.
    """
    version: str = PROMPT_VERSION

    @classmethod
    def build_system_instruction(cls) -> str:
        return (
            "You are GramSevak Weather Intelligence Advisory Generator. "
            "Your sole objective is to translate validated Gram Panchayat weather forecasts and "
            "deterministic agronomic rule evaluations into clear, actionable advice for farmers.\n\n"
            "STRICT OPERATIONAL & SAFETY CONSTRAINTS:\n"
            "1. NEVER invent, modify, round, or contradict numerical forecast values. The input downscaled rainfall is authoritative.\n"
            "2. NEVER invent crop diseases, pest outbreaks, or emergency situations outside the provided deterministic rules.\n"
            "3. NEVER prescribe specific chemical brand names or exact numeric chemical mixing dosages (e.g., '10 ml/acre').\n"
            "4. Follow the three-tier communication structure:\n"
            "   - Tier 1: What is happening (meteorological condition)\n"
            "   - Tier 2: Why it matters (agronomic impact on soil and crops)\n"
            "   - Tier 3: Recommended actions (concrete practical field steps)\n"
            "5. Return ONLY a valid JSON object conforming strictly to the requested schema. "
            "No markdown code fences, no explanations outside the JSON."
        )

    @classmethod
    def build_user_prompt(cls, input_contract: AIAdvisoryInputContract) -> str:
        p = input_contract.panchayat_context
        f = input_contract.forecast_context
        r = input_contract.deterministic_recommendations

        risks_summary = [
            {
                "rule_id": risk.rule_id,
                "risk_type": risk.risk_type,
                "severity": risk.severity.value,
                "condition": risk.triggering_condition,
            }
            for risk in input_contract.risks
        ]

        payload = {
            "panchayat": {
                "name": p.panchayat_name,
                "block": p.block_name,
                "district": p.district_name,
                "elevation_m": p.elevation_m,
            },
            "forecast": {
                "forecast_id": f.forecast_id,
                "forecast_date": str(f.forecast_date),
                "downscaled_rainfall_mm": f.downscaled_rainfall_mm,
                "block_forecast_rainfall_mm": f.block_forecast_rainfall_mm,
                "rainfall_category": f.rainfall_category,
                "lead_days": f.lead_days,
            },
            "deterministic_risks": risks_summary,
            "deterministic_recommendations": r.recommended_actions,
            "operational_guidance": r.operational_guidance,
            "timing_window": r.timing_window,
            "target_language": input_contract.target_language,
        }

        return (
            f"Generate a structured agricultural advisory in JSON format using the following validated context:\n"
            f"{json.dumps(payload, indent=2)}\n\n"
            "Required JSON Schema keys:\n"
            "- summary: str (10-500 chars)\n"
            "- what_is_happening: str (10-1000 chars)\n"
            "- why_it_matters: str (10-1000 chars)\n"
            "- recommended_actions: list of strings (>= 1 action)\n"
            "- timing: str\n"
            "- severity: str (LOW, MODERATE, HIGH, CRITICAL)\n"
            "- warnings: list of strings\n"
            "- supporting_forecast_reference: dict with forecast_id, forecast_date, downscaled_rainfall_mm"
        )


# =============================================================================
# 4. PROVIDER ABSTRACTION
# =============================================================================

class AIAdvisoryProvider(ABC):
    """
    Abstract base interface for AI providers (e.g. Mock, Ollama, OpenAI, Gemini).
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name identifier of the provider."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Active model identifier."""
        pass

    @property
    @abstractmethod
    def is_mock(self) -> bool:
        """True if the provider is a deterministic mock."""
        pass

    @abstractmethod
    def generate_advisory_text(
        self,
        system_instruction: str,
        user_prompt: str,
        timeout_seconds: float = 15.0,
    ) -> str:
        """
        Executes generation and returns raw response string (expected to be JSON).
        Raises AIProviderTimeoutError, AIProviderUnavailableError, AIProviderAuthError, etc.
        """
        pass


# =============================================================================
# 5. DETERMINISTIC MOCK PROVIDER
# =============================================================================

class MockAIAdvisoryProvider(AIAdvisoryProvider):
    """
    Deterministic mock provider for testing and local development.
    Produces strictly valid, grounded AIAdvisoryOutputContract JSON payloads
    without making external network calls.
    """

    def __init__(self, model_name: str = "mock-agricultural-advisor-v1"):
        self._model_name = model_name

    @property
    def provider_name(self) -> str:
        return "MOCK_AI_PROVIDER"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def is_mock(self) -> bool:
        return True

    def generate_advisory_text(
        self,
        system_instruction: str,
        user_prompt: str,
        timeout_seconds: float = 15.0,
    ) -> str:
        """
        Extracts values from the user prompt payload and generates deterministic output.
        """
        # Parse payload from prompt
        try:
            prompt_lines = user_prompt.split("\n", 1)[1]
            json_str = prompt_lines.split("\n\nRequired JSON Schema keys:")[0].strip()
            data = json.loads(json_str)
        except Exception:
            data = {}

        p_name = data.get("panchayat", {}).get("name", "Gram Panchayat")
        b_name = data.get("panchayat", {}).get("block", "Block")
        rf = float(data.get("forecast", {}).get("downscaled_rainfall_mm", 0.0))
        cat = data.get("forecast", {}).get("rainfall_category", "Rainfall")
        f_id = data.get("forecast", {}).get("forecast_id", 1)
        f_date = data.get("forecast", {}).get("forecast_date", "2026-09-10")
        recs = data.get("deterministic_recommendations", ["Maintain routine field monitoring."])
        timing = data.get("timing_window", "Next 24 to 48 hours")

        # Determine severity matching highest risk
        risks = data.get("deterministic_risks", [])
        if any(r.get("severity") == "CRITICAL" for r in risks):
            sev = "CRITICAL"
        elif any(r.get("severity") == "HIGH" for r in risks):
            sev = "HIGH"
        elif any(r.get("severity") == "MODERATE" for r in risks):
            sev = "MODERATE"
        else:
            sev = "LOW"

        # Deterministic articulation
        if rf > 115.5:
            summary = f"Extreme Rainfall Alert ({rf:.1f} mm): Immediate Field Suspension in {p_name}"
            what = f"Downscaled micro-forecast indicates very heavy to extreme precipitation of {rf:.1f} mm across {p_name}, {b_name}."
            why = "Rapid inundation and standing surface water will saturate topsoil, risking crop root hypoxia and severe soil erosion."
        elif rf > 64.4:
            summary = f"Heavy Rainfall Drainage Advisory ({rf:.1f} mm) for {p_name}"
            what = f"Heavy rainfall of {rf:.1f} mm is expected over {p_name}, {b_name}."
            why = "Soil moisture will reach full saturation, requiring proactive furrow drainage to prevent root-zone waterlogging."
        elif rf > 15.5:
            summary = f"Moderate Rainfall Operations Notice ({rf:.1f} mm) for {p_name}"
            what = f"Downscaled weather prediction indicates moderate rainfall of {rf:.1f} mm for {p_name}."
            why = "Active rainfall will wash away top-dressed fertilizers and cause tractor wheel compaction on wet field soil."
        elif rf > 2.5:
            summary = f"Light Rainfall Spraying Precaution ({rf:.1f} mm) in {p_name}"
            what = f"Light showers of {rf:.1f} mm are anticipated across {p_name}, {b_name}."
            why = "Foliar chemical sprays will be washed off plant foliage within 24 hours; soil moisture will be replenished naturally."
        elif rf > 0.0:
            summary = f"Very Light Showers ({rf:.1f} mm): Standard Farm Operations in {p_name}"
            what = f"Very light showers measuring {rf:.1f} mm are forecasted over {p_name}."
            why = "Trace surface moisture will not impede intercultural operations or scheduled chemical applications."
        else:
            summary = f"Dry Weather Farm Management Advisory for {p_name}"
            what = f"No significant precipitation (0.0 mm) is expected over {p_name}, {b_name}."
            why = "Unobstructed fieldwork conditions permit routine irrigation scheduling, weeding, and foliar spraying."

        warnings = []
        if rf > 2.5:
            warnings.append(f"Postpone chemical sprays due to expected {rf:.1f} mm rainfall wash-off risk.")
        if rf > 64.4:
            warnings.append("Inspect field drainage furrows to discharge standing water runoff.")

        output_dict = {
            "summary": summary,
            "what_is_happening": what,
            "why_it_matters": why,
            "recommended_actions": recs if recs else ["Maintain routine field monitoring."],
            "timing": timing,
            "severity": sev,
            "warnings": warnings,
            "supporting_forecast_reference": {
                "forecast_id": f_id,
                "forecast_date": f_date,
                "downscaled_rainfall_mm": rf,
            },
        }

        return json.dumps(output_dict)


# =============================================================================
# 6. HTTP JSON-SCHEMA PROVIDER (Ollama / OpenAI / Gemini Compatible)
# =============================================================================

class HttpAIAdvisoryProvider(AIAdvisoryProvider):
    """
    Standard HTTP JSON-Schema provider. Connects to Ollama (local) or cloud REST APIs.
    """

    def __init__(
        self,
        endpoint: str,
        model_name: str,
        api_key: Optional[str] = None,
        provider_name: str = "HTTP_GENERIC_PROVIDER",
    ):
        self._endpoint = endpoint.rstrip("/")
        self._model_name = model_name
        self._api_key = api_key
        self._provider_name = provider_name

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def is_mock(self) -> bool:
        return False

    def generate_advisory_text(
        self,
        system_instruction: str,
        user_prompt: str,
        timeout_seconds: float = 15.0,
    ) -> str:
        """
        Transmits request to HTTP provider and extracts response JSON text.
        """
        # Determine endpoint URL
        url = self._endpoint
        if not url.endswith("/chat/completions") and not url.endswith("/api/generate"):
            url = f"{url}/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "GramSevak-Advisory-Engine/1.0",
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        payload = {
            "model": self._model_name,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": settings.AI_ADVISORY_TEMPERATURE,
            "response_format": {"type": "json_object"},
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                resp_bytes = resp.read()
                resp_json = json.loads(resp_bytes.decode("utf-8"))
                # OpenAI format: choices[0].message.content
                if "choices" in resp_json and resp_json["choices"]:
                    return resp_json["choices"][0]["message"]["content"]
                # Ollama format: response
                if "response" in resp_json:
                    return resp_json["response"]
                raise AIOutputValidationError("Malformed provider payload: missing expected choices/response keys.")
        except urllib.error.HTTPError as err:
            if err.code in (401, 403):
                raise AIProviderAuthError(f"AI provider authentication failed (HTTP {err.code}).")
            elif err.code == 429:
                raise AIProviderRateLimitError("AI provider rate limit or quota exceeded (HTTP 429).")
            elif err.code in (500, 502, 503, 504):
                raise AIProviderUnavailableError(f"AI provider service unavailable (HTTP {err.code}).")
            else:
                raise AIAdvisoryServiceError(f"AI provider returned HTTP {err.code}: {err.reason}")
        except (urllib.error.URLError, TimeoutError) as err:
            if "timed out" in str(err).lower():
                raise AIProviderTimeoutError(f"AI provider request timed out after {timeout_seconds}s.")
            raise AIProviderUnavailableError(f"AI provider network connection failed: {err}")


# =============================================================================
# 7. AI ADVISORY SERVICE COORDINATOR
# =============================================================================

class AIAdvisoryService:
    """
    Coordinates prompt construction, provider execution with bounded retries,
    strict JSON/schema parsing, and numerical forecast groundedness verification.
    """

    def __init__(
        self,
        provider: Optional[AIAdvisoryProvider] = None,
        max_retries: Optional[int] = None,
        timeout_seconds: Optional[float] = None,
    ):
        self.provider = provider or self._resolve_configured_provider()
        self.max_retries = max_retries if max_retries is not None else settings.AI_ADVISORY_MAX_RETRIES
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else settings.AI_ADVISORY_TIMEOUT_SECONDS

    @classmethod
    def _resolve_configured_provider(cls) -> AIAdvisoryProvider:
        """Instantiates provider based on application settings."""
        prov_type = (settings.AI_ADVISORY_PROVIDER or "mock").lower().strip()
        model = settings.AI_ADVISORY_MODEL or "mock-agricultural-advisor-v1"

        if prov_type in ("mock", "test"):
            return MockAIAdvisoryProvider(model_name=model)
        elif prov_type in ("ollama", "http", "openai", "gemini"):
            endpoint = settings.AI_ADVISORY_ENDPOINT or "http://localhost:11434"
            return HttpAIAdvisoryProvider(
                endpoint=endpoint,
                model_name=model,
                api_key=settings.AI_ADVISORY_API_KEY,
                provider_name=f"HTTP_{prov_type.upper()}",
            )
        else:
            logger.warning(f"Unknown AI provider '{prov_type}', falling back to MockAIAdvisoryProvider.")
            return MockAIAdvisoryProvider(model_name=model)

    def compute_context_fingerprint(self, input_contract: AIAdvisoryInputContract) -> str:
        """Computes a deterministic hash fingerprint representing the exact input context."""
        p = input_contract.panchayat_context
        f = input_contract.forecast_context
        fingerprint_data = (
            f"P:{p.panchayat_id}|F:{f.forecast_id}|DATE:{f.forecast_date}|"
            f"RF:{f.downscaled_rainfall_mm:.2f}|PROMPT:{PROMPT_VERSION}|"
            f"LANG:{input_contract.target_language}"
        )
        return hashlib.sha256(fingerprint_data.encode("utf-8")).hexdigest()[:16]

    def _parse_and_validate_output(
        self,
        raw_text: str,
        input_contract: AIAdvisoryInputContract,
    ) -> AIAdvisoryOutputContract:
        """
        Parses raw text into JSON, validates schema fields, and enforces
        numerical weather groundedness.
        """
        # 1. Strip potential markdown fences if provider returned markdown
        clean_text = raw_text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        elif clean_text.startswith("```"):
            clean_text = clean_text[3:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
        clean_text = clean_text.strip()

        # 2. Parse JSON
        try:
            data = json.loads(clean_text)
        except json.JSONDecodeError as exc:
            raise AIOutputValidationError(
                f"AI provider response is not valid JSON: {exc}",
                details={"raw_text": raw_text[:200]},
            )

        if not isinstance(data, dict):
            raise AIOutputValidationError("AI provider response root must be a JSON object.")

        # 3. Validate against Pydantic schema
        try:
            output = AIAdvisoryOutputContract(**data)
        except Exception as exc:
            raise AIOutputValidationError(
                f"AI advisory output failed schema validation: {exc}",
                details={"error": str(exc)},
            )

        # 4. Strict Forecast Groundedness Invariant Verification
        f_ref = output.supporting_forecast_reference
        expected_rf = input_contract.forecast_context.downscaled_rainfall_mm
        expected_f_id = input_contract.forecast_context.forecast_id

        if not isinstance(f_ref, dict):
            raise ForecastGroundednessViolationError(
                "supporting_forecast_reference must be a valid dictionary.",
                details={"reference": f_ref},
            )

        actual_rf = f_ref.get("downscaled_rainfall_mm")
        if actual_rf is None or not isinstance(actual_rf, (int, float)):
            raise ForecastGroundednessViolationError(
                "supporting_forecast_reference must contain numerical downscaled_rainfall_mm.",
                details={"reference": f_ref},
            )

        if abs(float(actual_rf) - expected_rf) > 0.05:
            raise ForecastGroundednessViolationError(
                f"AI altered forecast rainfall! Expected {expected_rf:.2f} mm, but AI reported {actual_rf:.2f} mm.",
                details={"expected_rainfall": expected_rf, "reported_rainfall": actual_rf},
            )

        return output

    def generate_advisory(
        self,
        context: Union[AdvisoryContext, AIAdvisoryInputContract],
        target_language: str = "en",
    ) -> AIAdvisoryResult:
        """
        Executes end-to-end AI advisory generation for the given context.

        Args:
            context: Validated AdvisoryContext or AIAdvisoryInputContract.
            target_language: Language code ('en', 'mr', 'hi').

        Returns:
            AIAdvisoryResult: Validated structured advisory and audit metadata.
        """
        # Convert AdvisoryContext to AIAdvisoryInputContract if needed
        if isinstance(context, AdvisoryContext):
            input_contract = context.to_ai_input(target_language=target_language)
        elif isinstance(context, AIAdvisoryInputContract):
            input_contract = context
        else:
            raise AIAdvisoryServiceError(f"Unsupported context type '{type(context)}'.")

        fingerprint = self.compute_context_fingerprint(input_contract)

        system_instruction = AdvisoryPromptBuilder.build_system_instruction()
        user_prompt = AdvisoryPromptBuilder.build_user_prompt(input_contract)

        start_time = time.time()
        retries_taken = 0
        last_error: Optional[Exception] = None

        # Bounded retry loop for transient network/timeout errors
        for attempt in range(self.max_retries + 1):
            try:
                raw_response = self.provider.generate_advisory_text(
                    system_instruction=system_instruction,
                    user_prompt=user_prompt,
                    timeout_seconds=self.timeout_seconds,
                )
                output = self._parse_and_validate_output(raw_response, input_contract)
                latency = round((time.time() - start_time) * 1000, 2)

                meta = AIExecutionMetadata(
                    provider_name=self.provider.provider_name,
                    model_name=self.provider.model_name,
                    prompt_version=PROMPT_VERSION,
                    latency_ms=latency,
                    status="SUCCESS",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    is_mock=self.provider.is_mock,
                    retries_taken=attempt,
                    context_fingerprint=fingerprint,
                )
                return AIAdvisoryResult(output=output, metadata=meta)

            except (AIProviderTimeoutError, AIProviderUnavailableError) as transient_err:
                retries_taken = attempt
                last_error = transient_err
                if attempt < self.max_retries:
                    backoff = 0.5 * (2 ** attempt)
                    logger.warning(
                        f"[AI_ADVISORY_RETRY] Attempt {attempt + 1} failed ({transient_err.code}). "
                        f"Retrying in {backoff:.2f}s..."
                    )
                    time.sleep(backoff)
                else:
                    break
            except (AIProviderAuthError, AIProviderConfigError, AIOutputValidationError, ForecastGroundednessViolationError) as permanent_err:
                # Do NOT retry permanent configuration, authentication, or validation errors
                last_error = permanent_err
                break

        latency = round((time.time() - start_time) * 1000, 2)
        logger.error(f"[AI_ADVISORY_GENERATION_FAILED] fingerprint={fingerprint} error={last_error}")
        if last_error:
            raise last_error
        raise AIAdvisoryServiceError("AI advisory generation failed with unknown error.")


# Application-wide default singleton instance
default_ai_advisory_service = AIAdvisoryService()


def get_ai_advisory_provider() -> AIAdvisoryProvider:
    """Convenience factory function returning the configured AIAdvisoryProvider."""
    return AIAdvisoryService._resolve_configured_provider()
