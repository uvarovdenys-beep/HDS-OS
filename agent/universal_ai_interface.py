#!/usr/bin/env python3
"""
universal_ai_interface.py
HDS6 Universal AI Interface - Standardized AI integration

Authors: HDS6 Development Team
License: HDS6 Standard - R-Series Laws Enforced
"""

import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Union
import asyncio
import hashlib
import requests

class AIFramework(Enum):
    """Supported AI frameworks."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    LOCAL = "local"
    OLLAMA = "ollama"
    LMS = "lms"
    CUSTOM = "custom"

class AIRequestType(Enum):
    """Types of AI requests."""
    TEXT_GENERATION = "text_generation"
    CODE_GENERATION = "code_generation"
    ANALYSIS = "analysis"
    TRANSLATION = "translation"
    SUMMARIZATION = "summarization"
    CLASSIFICATION = "classification"

@dataclass
class AIRequest:
    """AI request structure."""
    request_id: str
    framework: AIFramework
    request_type: AIRequestType
    prompt: str
    context: Optional[Dict[str, Any]] = None
    parameters: Optional[Dict[str, Any]] = None
    timeout: float = 30.0
    max_tokens: int = 1000
    temperature: float = 0.7

@dataclass
class AIResponse:
    """AI response structure."""
    request_id: str
    success: bool
    content: str
    usage: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    processing_time: float = 0.0
    model_used: Optional[str] = None

class AIProvider(ABC):
    """Abstract base class for AI providers."""
    
    def __init__(self, provider_id: str, config: Dict[str, Any]):
        self.provider_id = provider_id
        self.config = config
        self.logger = logging.getLogger(f"HDS6.AI.{provider_id}")
        self.request_history: List[AIRequest] = []
        self.response_cache: Dict[str, AIResponse] = {}
        self.rate_limiter = None
        
        # Smart caching persistence
        self.cache_file = Path(config.get("cache_file", f"ai-mind/cache/{provider_id}_cache.json"))
        self._load_cache()
    
    def _load_cache(self):
        """Load cache from disk."""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    for k, v in cached_data.items():
                        self.response_cache[k] = AIResponse(**v)
        except Exception as e:
            self.logger.warning(f"Failed to load cache for {self.provider_id}: {e}")

    def _save_cache(self):
        """Save cache to disk."""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            serializable_cache = {k: v.__dict__ for k, v in self.response_cache.items()}
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(serializable_cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.warning(f"Failed to save cache for {self.provider_id}: {e}")

    @abstractmethod
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate AI response."""
        raise NotImplementedError("AI provider must implement generate_response() method")
    
    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate provider configuration."""
        raise NotImplementedError("AI provider must implement validate_config() method")
    
    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """Get supported capabilities."""
        raise NotImplementedError("AI provider must implement get_capabilities() method")
    
    def cache_response(self, request: AIRequest, response: AIResponse):
        """Cache response for reuse."""
        cache_key = self._generate_cache_key(request)
        self.response_cache[cache_key] = response
        self._save_cache()
    
    def get_cached_response(self, request: AIRequest) -> Optional[AIResponse]:
        """Get cached response for request."""
        cache_key = self._generate_cache_key(request)
        return self.response_cache.get(cache_key)
    
    def _generate_cache_key(self, request: AIRequest) -> str:
        """Generate cache key for request."""
        key_data = f"{request.framework.value}:{request.request_type.value}:{request.prompt}:{request.parameters}"
        return hashlib.md5(key_data.encode()).hexdigest()

def _resolve_secret(value: str, *env_fallbacks: str) -> str:
    """Resolve a server-AI key WITHOUT keeping it in a committed file.

    - "${VAR}"            -> os.environ["VAR"]
    - "" / placeholder    -> first non-empty env fallback (e.g. OPENAI_API_KEY)
    - raw key in file     -> returned as-is (discouraged: ai_providers.json is
                             not gitignored; prefer env vars so keys never leak
                             into the git-pushed deploy).
    """
    import os
    import re
    v = (value or "").strip()
    m = re.fullmatch(r"\$\{([A-Z0-9_]+)\}", v)
    if m:
        return os.environ.get(m.group(1), "")
    if not v or v == "YOUR_API_KEY_HERE":
        for env in env_fallbacks:
            if os.environ.get(env):
                return os.environ[env]
        return ""
    return v


class OpenAIProvider(AIProvider):
    """OpenAI provider implementation."""

    def __init__(self, provider_id: str, config: Dict[str, Any]):
        super().__init__(provider_id, config)
        self.api_key = _resolve_secret(
            config.get("api_key", ""), "HDS_OPENAI_KEY", "OPENAI_API_KEY")
        self.base_url = config.get("base_url", "https://api.openai.com/v1")
        self.default_model = config.get("default_model", "gpt-3.5-turbo")
    
    def validate_config(self) -> bool:
        """Validate OpenAI configuration."""
        return bool(self.api_key)
    
    def get_capabilities(self) -> List[AIRequestType]:
        """Get OpenAI capabilities."""
        return [
            AIRequestType.TEXT_GENERATION,
            AIRequestType.CODE_GENERATION,
            AIRequestType.ANALYSIS,
            AIRequestType.TRANSLATION,
            AIRequestType.SUMMARIZATION,
            AIRequestType.CLASSIFICATION
        ]
    
    async def generate_response(self, request: AIRequest) -> AIResponse:
        """Generate response using OpenAI."""
        start_time = time.time()
        
        try:
            # Simulate OpenAI API call
            await asyncio.sleep(0.1)  # Simulate network delay
            
            # Generate mock response
            content = f"OpenAI response to: {request.prompt[:50]}..."
            
            processing_time = time.time() - start_time
            
            return AIResponse(
                request_id=request.request_id,
                success=True,
                content=content,
                usage={"prompt_tokens": len(request.prompt), "completion_tokens": len(content)},
                processing_time=processing_time,
                model_used=self.default_model
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            return AIResponse(
                request_id=request.request_id,
                success=False,
                content="",
                error_message=str(e),
                processing_time=processing_time
            )

class LocalAIProvider(AIProvider):
    """Local AI provider implementation - REAL MODEL CALLS via Ollama/LMS."""

    def __init__(self, provider_id: str, config: Dict[str, Any]):
        super().__init__(provider_id, config)
        self.base_url = config.get("base_url", "http://localhost:11434")
        self.model = config.get("model", "qwen:7b")
        self.timeout = config.get("timeout", 300)
        self.is_lms = ":1234" in self.base_url

    def validate_config(self) -> bool:
        """Validate local AI configuration."""
        try:
            if self.is_lms:
                response = requests.get(f"{self.base_url}/models", timeout=5)
            else:
                response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception as e:
            self.logger.warning(f"Local model check failed: {e}")
            return False

    def get_capabilities(self) -> List[AIRequestType]:
        """Get local AI capabilities."""
        return [
            AIRequestType.TEXT_GENERATION,
            AIRequestType.CODE_GENERATION,
            AIRequestType.ANALYSIS
        ]

    async def generate_response(self, request: AIRequest) -> AIResponse:
        """Generate REAL response using local model via Ollama or LM Studio."""
        start_time = time.time()

        try:
            if self.is_lms:
                content = await self._call_lms(request.prompt)
            else:
                content = await self._call_ollama(request.prompt)

            processing_time = time.time() - start_time

            return AIResponse(
                request_id=request.request_id,
                success=True,
                content=content,
                usage={"prompt_tokens": len(request.prompt), "completion_tokens": len(content)},
                processing_time=processing_time,
                model_used=self.model
            )

        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"LocalAIProvider error: {e}")
            return AIResponse(
                request_id=request.request_id,
                success=False,
                content="",
                error_message=str(e),
                processing_time=processing_time
            )

    async def _call_ollama(self, prompt: str) -> str:
        """Call real Ollama API."""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(
                    f"{self.base_url}/api/generate",
                    json={"model": self.model, "prompt": prompt, "stream": False},
                    timeout=self.timeout
                )
            )

            if response.status_code == 200:
                return response.json().get("response", "")
            else:
                raise Exception(f"Ollama error: {response.status_code}")
        except requests.exceptions.ConnectionError:
            raise Exception(f"Cannot connect to Ollama at {self.base_url}. Start with: ollama run {self.model}")
        except requests.exceptions.Timeout:
            raise Exception(f"Ollama timeout (>{self.timeout}s). Model may be overloaded.")

    async def _call_lms(self, prompt: str) -> str:
        """Call real LM Studio API."""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(
                    f"{self.base_url}/completions",
                    json={"prompt": prompt, "max_tokens": 2000, "temperature": 0.3},
                    timeout=self.timeout
                )
            )

            if response.status_code == 200:
                return response.json().get("choices", [{}])[0].get("text", "")
            else:
                raise Exception(f"LM Studio error: {response.status_code}")
        except requests.exceptions.ConnectionError:
            raise Exception(f"Cannot connect to LM Studio at {self.base_url}. Start LM Studio server.")
        except requests.exceptions.Timeout:
            raise Exception(f"LM Studio timeout (>{self.timeout}s)")

class OllamaProvider(AIProvider):
    """Ollama local AI provider - REAL CALLS."""

    def __init__(self, provider_id: str, config: Dict[str, Any]):
        super().__init__(provider_id, config)
        self.base_url = config.get("base_url", "http://localhost:11434")
        self.default_model = config.get("default_model", "qwen:7b")
        self.timeout = config.get("timeout", 300)

    def validate_config(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False

    def get_capabilities(self) -> List[AIRequestType]:
        return [AIRequestType.TEXT_GENERATION, AIRequestType.CODE_GENERATION, AIRequestType.ANALYSIS]

    async def generate_response(self, request: AIRequest) -> AIResponse:
        start_time = time.time()
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(
                    f"{self.base_url}/api/generate",
                    json={"model": self.default_model, "prompt": request.prompt, "stream": False},
                    timeout=self.timeout
                )
            )

            if response.status_code == 200:
                content = response.json().get("response", "")
            else:
                raise Exception(f"Ollama API error: {response.status_code}")

            return AIResponse(
                request.request_id,
                True,
                content,
                processing_time=time.time()-start_time,
                model_used=self.default_model
            )
        except Exception as e:
            self.logger.error(f"Ollama error: {e}")
            return AIResponse(
                request.request_id,
                False,
                "",
                error_message=str(e),
                processing_time=time.time()-start_time
            )

class LMSProvider(AIProvider):
    """LM Studio (LMS) local AI provider - REAL CALLS."""

    def __init__(self, provider_id: str, config: Dict[str, Any]):
        super().__init__(provider_id, config)
        self.base_url = config.get("base_url", "http://localhost:1234/v1")
        self.timeout = config.get("timeout", 300)

    def validate_config(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/models", timeout=5)
            return response.status_code == 200
        except:
            return False

    def get_capabilities(self) -> List[AIRequestType]:
        return [AIRequestType.TEXT_GENERATION, AIRequestType.CODE_GENERATION]

    async def generate_response(self, request: AIRequest) -> AIResponse:
        start_time = time.time()
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(
                    f"{self.base_url}/completions",
                    json={"prompt": request.prompt, "max_tokens": 2000, "temperature": 0.3},
                    timeout=self.timeout
                )
            )

            if response.status_code == 200:
                content = response.json().get("choices", [{}])[0].get("text", "")
            else:
                raise Exception(f"LM Studio API error: {response.status_code}")

            return AIResponse(
                request.request_id,
                True,
                content,
                processing_time=time.time()-start_time,
                model_used="lms-server"
            )
        except Exception as e:
            self.logger.error(f"LMS error: {e}")
            return AIResponse(
                request.request_id,
                False,
                "",
                error_message=str(e),
                processing_time=time.time()-start_time
            )

class GoogleGeminiProvider(AIProvider):
    """Google Gemini AI provider."""
    
    def __init__(self, provider_id: str, config: Dict[str, Any]):
        super().__init__(provider_id, config)
        self.api_key = _resolve_secret(
            config.get("api_key", ""), "HDS_GEMINI_KEY", "GOOGLE_API_KEY",
            "GEMINI_API_KEY")
        self.default_model = config.get("default_model", "gemini-pro")
    
    def validate_config(self) -> bool:
        return bool(self.api_key)
        
    def get_capabilities(self) -> List[AIRequestType]:
        return [AIRequestType.TEXT_GENERATION, AIRequestType.CODE_GENERATION, AIRequestType.ANALYSIS]
        
    async def generate_response(self, request: AIRequest) -> AIResponse:
        start_time = time.time()
        # Mocking Gemini call with Vision support check
        is_vision = request.context and request.context.get("image_path")
        model = "gemini-pro-vision" if is_vision else self.default_model
        content = f"[GEMINI:{model}] Hybrid response for: {request.prompt[:30]}"
        return AIResponse(request.request_id, True, content, processing_time=time.time()-start_time, model_used=model)

class HDSUniversalAIInterface:
    """
    Universal AI interface for HDS6.
    
    Features:
    - Multi-framework support
    - Intelligent provider selection
    - Request routing and load balancing
    - Response caching
    - Usage monitoring
    - Failover capabilities
    """
    
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.logger = logging.getLogger(__name__)
        
        # Provider management
        self.providers: Dict[str, AIProvider] = {}
        self.provider_priorities: Dict[AIFramework, List[str]] = {}
        self.active_requests: Dict[str, AIRequest] = {}
        
        # Configuration
        self.config_file = self.base_dir / "ai-mind" / "config" / "ai_providers.json"
        self.cache_enabled = True
        self.max_cache_size = 1000
        self.request_timeout = 30.0
        
        # Statistics
        self.request_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "average_response_time": 0.0,
            "provider_usage": {},
            "request_types": {}
        }
        
        self.logger.info("HDS6 Universal AI Interface initialized")
    
    def load_configuration(self) -> bool:
        """Load AI provider configuration."""
        try:
            if not self.config_file.exists():
                self._create_default_config()
                return True
            
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            
            # Load providers
            for provider_config in config.get("providers", []):
                self._add_provider(provider_config)
            
            # Load priorities
            for req_type_str, provider_list in config.get("priorities", {}).items():
                try:
                    self.provider_priorities[AIRequestType(req_type_str)] = provider_list
                except ValueError:
                    self.logger.warning(f"Invalid AIRequestType in priorities: {req_type_str}")
            
            self.logger.info(f"Loaded {len(self.providers)} AI providers")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load AI configuration: {e}")
            return False
    
    def _create_default_config(self):
        """Create default AI provider configuration."""
        default_config = {
            "providers": [
                {
                    "provider_id": "openai_primary",
                    "framework": "openai",
                    "config": {
                        "api_key": "YOUR_API_KEY_HERE",
                        "base_url": "https://api.openai.com/v1",
                        "default_model": "gpt-3.5-turbo"
                    },
                    "enabled": True
                },
                {
                    "provider_id": "local_fallback",
                    "framework": "local",
                    "config": {
                        "model_path": "./models/local_model",
                        "model_type": "transformer"
                    },
                    "enabled": True
                }
            ],
            "priorities": {
                "text_generation": ["openai_primary", "local_fallback"],
                "code_generation": ["openai_primary", "local_fallback"],
                "analysis": ["openai_primary", "local_fallback"]
            }
        }
        
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(default_config, f, indent=2)
    
    def _add_provider(self, provider_config: Dict[str, Any]):
        """Add AI provider."""
        try:
            provider_id = provider_config["provider_id"]
            framework = AIFramework(provider_config["framework"])
            config = provider_config["config"]
            enabled = provider_config.get("enabled", True)
            
            if not enabled:
                return
            
            # Create provider instance
            if framework == AIFramework.OPENAI:
                provider = OpenAIProvider(provider_id, config)
            elif framework == AIFramework.LOCAL:
                provider = LocalAIProvider(provider_id, config)
            elif framework == AIFramework.OLLAMA:
                provider = OllamaProvider(provider_id, config)
            elif framework == AIFramework.LMS:
                provider = LMSProvider(provider_id, config)
            elif framework == AIFramework.GOOGLE:
                provider = GoogleGeminiProvider(provider_id, config)
            else:
                self.logger.warning(f"Unsupported framework: {framework}")
                return
            
            # Validate configuration
            if not provider.validate_config():
                self.logger.error(f"Provider validation failed: {provider_id}")
                return
            
            self.providers[provider_id] = provider
            self.logger.info(f"Added AI provider: {provider_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to add provider: {e}")
    
    async def process_request(self, request: AIRequest) -> AIResponse:
        """Process AI request with intelligent routing."""
        start_time = time.time()
        
        try:
            # Update statistics
            self._update_request_stats(request)
            
            # Check cache first
            if self.cache_enabled:
                cached_response = self._get_cached_response(request)
                if cached_response:
                    self.logger.info(f"Cache hit for request: {request.request_id}")
                    return cached_response
            
            # Select best provider
            provider = await self._select_provider(request)
            if not provider:
                return AIResponse(
                    request_id=request.request_id,
                    success=False,
                    content="",
                    error_message="No suitable provider found"
                )
            
            # Process request
            response = await provider.generate_response(request)
            
            # Cache successful response
            if self.cache_enabled and response.success:
                self._cache_response(request, response)
            
            # Update statistics
            self._update_response_stats(response, time.time() - start_time)
            
            self.logger.info(f"AI request processed: {request.request_id} - Success: {response.success}")
            return response
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"AI request failed: {request.request_id} - {e}")
            return AIResponse(
                request_id=request.request_id,
                success=False,
                content="",
                error_message=str(e),
                processing_time=processing_time
            )
    
    async def _select_provider(self, request: AIRequest) -> Optional[AIProvider]:
        """
        Intelligent provider selection for HDS.
        Prioritizes LOCAL for analysis/code validation to save tokens.
        """
        # Hybrid routing logic
        if request.request_type in [AIRequestType.ANALYSIS, AIRequestType.CLASSIFICATION]:
            # Always try local first for these types
            for p_id, p in self.providers.items():
                if isinstance(p, LocalAIProvider) and p.validate_config():
                    return p

        # Get provider priorities for request type
        priorities = self.provider_priorities.get(request.request_type, [])
        
        # Try providers in priority order
        for provider_id in priorities:
            provider = self.providers.get(provider_id)
            if provider and request.request_type in provider.get_capabilities():
                return provider
        
        # Fallback: use any available provider
        for provider in self.providers.values():
            if request.request_type in provider.get_capabilities():
                return provider
        
        return None
    
    def _get_cached_response(self, request: AIRequest) -> Optional[AIResponse]:
        """Get cached response if available."""
        for provider in self.providers.values():
            cached_response = provider.get_cached_response(request)
            if cached_response:
                return cached_response
        return None
    
    def _cache_response(self, request: AIRequest, response: AIResponse):
        """Cache response for future use."""
        for provider in self.providers.values():
            if request.request_type in provider.get_capabilities():
                provider.cache_response(request, response)
                break # Cache only in one suitable provider
    
    def _update_request_stats(self, request: AIRequest):
        """Update request statistics."""
        self.request_stats["total_requests"] += 1
        
        # Update provider usage
        if request.framework.value not in self.request_stats["provider_usage"]:
            self.request_stats["provider_usage"][request.framework.value] = 0
        self.request_stats["provider_usage"][request.framework.value] += 1
        
        # Update request types
        if request.request_type.value not in self.request_stats["request_types"]:
            self.request_stats["request_types"][request.request_type.value] = 0
        self.request_stats["request_types"][request.request_type.value] += 1
    
    def _update_response_stats(self, response: AIResponse, processing_time: float):
        """Update response statistics."""
        if response.success:
            self.request_stats["successful_requests"] += 1
        else:
            self.request_stats["failed_requests"] += 1
        
        # Update average response time
        total_requests = self.request_stats["total_requests"]
        current_avg = self.request_stats["average_response_time"]
        self.request_stats["average_response_time"] = (
            (current_avg * (total_requests - 1) + processing_time) / total_requests
        )
    
    def get_interface_stats(self) -> Dict[str, Any]:
        """Get interface statistics."""
        return {
            "total_requests": self.request_stats["total_requests"],
            "successful_requests": self.request_stats["successful_requests"],
            "failed_requests": self.request_stats["failed_requests"],
            "success_rate": (
                self.request_stats["successful_requests"] / self.request_stats["total_requests"] * 100
            ) if self.request_stats["total_requests"] > 0 else 0,
            "average_response_time": self.request_stats["average_response_time"],
            "provider_usage": self.request_stats["provider_usage"],
            "request_types": self.request_stats["request_types"],
            "active_providers": len(self.providers)
        }
    
    def get_provider_status(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """Get provider status."""
        provider = self.providers.get(provider_id)
        if not provider:
            return None
        
        return {
            "provider_id": provider_id,
            "framework": provider.__class__.__name__,
            "capabilities": [cap.value for cap in provider.get_capabilities()],
            "validated": provider.validate_config()
        }
    
    def create_request(self, 
                      request_type: AIRequestType,
                      prompt: str,
                      framework: Optional[AIFramework] = None,
                      **kwargs) -> AIRequest:
        """Create standardized AI request."""
        request_id = f"ai_req_{int(time.time() * 1000000)}"
        
        # Auto-select framework if not specified
        if not framework:
            framework = AIFramework.LOCAL  # Default to local
        
        return AIRequest(
            request_id=request_id,
            framework=framework,
            request_type=request_type,
            prompt=prompt,
            **kwargs
        )

# Global AI interface instance
ai_interface = None

def get_ai_interface(base_dir: Optional[Path] = None) -> HDSUniversalAIInterface:
    """Get global AI interface instance."""
    global ai_interface
    if ai_interface is None:
        if base_dir is None:
            base_dir = Path(__file__).parent.parent
        ai_interface = HDSUniversalAIInterface(base_dir)
        ai_interface.load_configuration()
    return ai_interface