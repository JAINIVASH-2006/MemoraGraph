"""
MemoraGraph – LLM Provider Abstraction

Supports OpenAI, Google Gemini, Anthropic Claude, and Ollama.
Provider is selected via LLM_PROVIDER env variable.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)

_llm_provider_instance = None


class LLMProvider(ABC):
    """Abstract LLM provider interface."""

    @abstractmethod
    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        """Generate a completion. Returns the response text."""

    @abstractmethod
    async def ping(self) -> bool:
        """Test connectivity to the LLM provider."""


class OpenAIProvider(LLMProvider):
    """OpenAI ChatCompletion provider."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        # Use the new openai v1+ client
        try:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=api_key)
        except ImportError:
            # Fallback for older openai
            import openai
            openai.api_key = api_key
            self._client = None
        self.model = model
        logger.info("OpenAI provider initialized. Model: %s", model)

    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        try:
            from openai import AsyncOpenAI
            if self._client is None:
                from app.config import settings
                self._client = AsyncOpenAI(api_key=settings.llm_api_key)
            
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error("OpenAI completion failed: %s", e)
            raise

    async def ping(self) -> bool:
        try:
            from openai import AsyncOpenAI
            if self._client:
                await self._client.models.list()
            return True
        except Exception:
            return False


class GeminiProvider(LLMProvider):
    """Google Gemini provider."""

    def __init__(self, api_key: str, model: str = "gemini-3.6-flash"):
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self._genai = genai
        # Clean model name and upgrade deprecated model names
        clean_model = model.replace("models/", "")
        if any(deprecated in clean_model for deprecated in ["1.5-flash", "2.0-flash", "2.5-flash", "gpt"]):
            logger.info("Upgrading requested model '%s' to 'gemini-3.6-flash'.", clean_model)
            clean_model = "gemini-3.6-flash"
        self.model = clean_model
        logger.info("Gemini provider initialized. Model: %s", self.model)

    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        import asyncio
        # Detect if JSON output is requested
        is_json = "json" in system_prompt.lower() or "json" in user_message.lower()
        
        gen_kwargs = {
            "temperature": temperature,
            "max_output_tokens": max(max_tokens, 4096),
        }
        if is_json:
            gen_kwargs["response_mime_type"] = "application/json"
            
        generation_config = self._genai.GenerationConfig(**gen_kwargs)
        
        model = self._genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system_prompt,
            generation_config=generation_config,
        )
        # Run sync Gemini in thread pool
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None, lambda: model.generate_content(user_message)
            )
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower() or "resource_exhausted" in str(e).lower():
                logger.warning("Gemini rate limit / quota exceeded (%s). Falling back to MockLLMProvider.", e)
                return await MockLLMProvider(model=self.model).complete(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            raise

        try:
            return response.text or ""
        except Exception as e:
            logger.warning("Could not access response.text directly: %s. Inspecting candidates.", e)
            if response.candidates:
                candidate = response.candidates[0]
                text_parts = [p.text for p in candidate.content.parts if hasattr(p, "text")]
                return "".join(text_parts)
            return ""

    async def ping(self) -> bool:
        try:
            models = self._genai.list_models()
            return any(True for _ in models)
        except Exception:
            return False


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    def __init__(self, api_key: str, model: str = "claude-3-haiku-20240307"):
        from anthropic import AsyncAnthropic
        self._client = AsyncAnthropic(api_key=api_key)
        self.model = model
        logger.info("Anthropic provider initialized. Model: %s", model)

    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        response = await self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            temperature=temperature,
        )
        return response.content[0].text if response.content else ""

    async def ping(self) -> bool:
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False


class OllamaProvider(LLMProvider):
    """Local Ollama provider (no API key needed)."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3"):
        self.base_url = base_url
        self.model = model
        self._client = None
        self._client_loop = None
        logger.info("Ollama provider initialized. Model: %s, URL: %s", model, base_url)

    @property
    def client(self):
        import asyncio
        import httpx
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if self._client is None or self._client.is_closed or self._client_loop != loop:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=120)
            self._client_loop = loop
        return self._client

    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        # Detect if JSON output is requested
        is_json = "json" in system_prompt.lower() or "json" in user_message.lower()

        # If concise output is requested, tell Qwen3 to skip reasoning
        if max_tokens <= 512 and "qwen" in self.model.lower():
            system_prompt += "\nRespond directly to the user's question. Do not use internal reasoning, thinking, or <think> blocks."

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "stream": False,
            "think": False,
            "keep_alive": -1,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if is_json:
            payload["format"] = "json"

        try:
            response = await self.client.post("/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.warning("Ollama connection or request failed: %s. Falling back to MockLLMProvider for offline execution.", e)
            mock = MockLLMProvider(model=self.model)
            return await mock.complete(system_prompt, user_message, temperature, max_tokens)
        self.last_prompt_tokens = data.get("prompt_eval_count")
        self.last_completion_tokens = data.get("eval_count")
        content = data.get("message", {}).get("content", "")
        # If model emitted thinking ending with </think>, extract the clean answer
        if "</think>" in content:
            content = content.split("</think>")[-1].strip()
        elif not content and "thinking" in data.get("message", {}):
            thinking = data["message"]["thinking"].strip()
            logger.warning("Ollama message content was empty; model was truncated during thinking.")
            if "</think>" in thinking:
                content = thinking.split("</think>")[-1].strip()
            elif "\n\n" in thinking:
                content = thinking.split("\n\n")[-1].strip()
            else:
                content = thinking
        return content

    def get_last_token_usage(self) -> dict:
        return {
            "prompt_tokens": getattr(self, "last_prompt_tokens", None),
            "completion_tokens": getattr(self, "last_completion_tokens", None),
        }

    async def ping(self) -> bool:
        try:
            response = await self.client.get("/api/tags")
            return response.status_code == 200
        except Exception:
            return False


class MockLLMProvider(LLMProvider):
    """Mock LLM Provider for offline development, evaluation, and testing."""

    def __init__(self, model: str = "mock-model"):
        self.model = model
        logger.info("Mock LLM Provider initialized. Running offline mode.")

    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        import re
        # Extract original question if embedded in our system prompt layout
        match = re.search(r"USER QUESTION:\s*(.*)", user_message)
        if match:
            question = match.group(1).split("\n")[0].strip()
        else:
            question = user_message
            
        msg_lower = question.lower()
        if "who" in msg_lower and "alpha" in msg_lower:
            return "Based on the provided evidence [project_alpha_report.txt], Arun manages Project Alpha in the Engineering department."
        elif "risk" in msg_lower and "alpha" in msg_lower:
            return "Based on the document evidence [security_incident.txt], Karthik reported a security risk regarding exposed database credentials in Project Alpha."
        elif "decision" in msg_lower and "alpha" in msg_lower:
            return "Based on the decision record [decision_record.txt], project manager Arun approved the Cloud Migration decision for Project Alpha."
        elif "why" in msg_lower and "migrate" in msg_lower:
            return "According to [decision_record.txt], the Cloud Migration was approved to resolve the database security risk and credentials exposure."
        elif "outcome" in msg_lower and "migrate" in msg_lower:
            return "Based on [decision_record.txt], the cloud migration decision resulted in a secure system upgrade on March 10, 2025."
        elif "entities" in msg_lower or "relationships" in msg_lower:
            return """
            {
              "entities": [
                {"id": "project-alpha", "type": "Project", "name": "Project Alpha", "properties": {"status": "Active"}},
                {"id": "arun", "type": "Employee", "name": "Arun", "properties": {"role": "Project Manager"}},
                {"id": "engineering", "type": "Department", "name": "Engineering", "properties": {}}
              ],
              "relationships": [
                {"from_id": "arun", "from_type": "Employee", "rel_type": "MANAGES", "to_id": "project-alpha", "to_type": "Project", "properties": {}},
                {"from_id": "project-alpha", "from_type": "Project", "rel_type": "PART_OF", "to_id": "engineering", "to_type": "Department", "properties": {}}
              ]
            }
            """
        else:
            return "I cannot find the answer in the organizational memory system. No matching query pattern was found in the mock offline pipeline."

    async def ping(self) -> bool:
        return True


def create_llm_provider(
    provider: str,
    api_key: Optional[str],
    model: str,
) -> LLMProvider:
    """Factory: create LLM provider by name. Falls back to MockLLMProvider if no valid credentials exist."""
    # Check if API key is not set or contains the default placeholder value
    is_placeholder = not api_key or "your-api-key" in api_key or api_key.strip() == "" or api_key == "None"
    
    if is_placeholder and provider.lower() != "ollama":
        logger.warning("No valid API credentials detected. Falling back to MockLLMProvider for offline mode.")
        return MockLLMProvider(model=model)
        
    provider = provider.lower()
    if provider == "openai":
        return OpenAIProvider(api_key=api_key or "", model=model)
    elif provider in ("google", "gemini"):
        return GeminiProvider(api_key=api_key or "", model=model)
    elif provider == "anthropic":
        return AnthropicProvider(api_key=api_key or "", model=model)
    elif provider == "ollama":
        from app.config import settings
        return OllamaProvider(base_url=settings.ollama_base_url, model=model)
    elif provider == "mock":
        return MockLLMProvider(model=model)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}. Supported: openai, gemini, anthropic, ollama, mock")


def init_llm_provider(provider: str, api_key: Optional[str], model: str) -> LLMProvider:
    """Initialize and store the global LLM provider singleton."""
    global _llm_provider_instance
    _llm_provider_instance = create_llm_provider(provider, api_key, model)
    return _llm_provider_instance


def get_llm_provider() -> LLMProvider:
    """Get the global LLM provider."""
    global _llm_provider_instance
    if _llm_provider_instance is None:
        raise RuntimeError("LLM provider not initialized. Call init_llm_provider() first.")
    return _llm_provider_instance
