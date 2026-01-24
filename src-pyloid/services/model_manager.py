"""Model manager for loading and caching Llama models."""

import asyncio
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from llama_cpp import Llama

from config import get_settings
from utils.inference_utils import (
    detect_chat_format_from_filename,
    detect_gpu_support,
    detect_multimodal_model,
    estimate_memory_usage,
)


@dataclass
class ModelMetadata:
    """Metadata for a loaded model."""

    model_id: str
    path: Path
    chat_format: Optional[str]
    n_ctx: int
    n_gpu_layers: int
    loaded_at: float = field(default_factory=time.time)
    is_multimodal: bool = False
    multimodal_type: Optional[str] = None
    size_bytes: int = 0


class ModelManager:
    """Manages Llama model instances with caching and lifecycle management.
    
    This is a singleton service that handles model loading, caching, and unloading.
    It uses an LRU cache to manage memory by unloading least recently used models.
    """

    _instance: Optional["ModelManager"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "ModelManager":
        """Create singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize model manager."""
        if self._initialized:
            return

        self._models: OrderedDict[str, Llama] = OrderedDict()
        self._metadata: Dict[str, ModelMetadata] = {}
        self._loading_locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()
        self._initialized = True

    def _get_model_id(self, model_path: Path) -> str:
        """Generate model ID from path.
        
        Args:
            model_path: Path to the model file
            
        Returns:
            Model identifier string
        """
        return model_path.name

    def _resolve_model_path(self, model: str) -> Optional[Path]:
        """Resolve model identifier to file path.
        
        Args:
            model: Model identifier (filename or path)
            
        Returns:
            Resolved Path or None if not found
        """
        settings = get_settings()
        
        # If it's already an absolute path
        if Path(model).is_absolute():
            path = Path(model)
            if path.exists() and path.suffix.lower() == ".gguf":
                return path
            return None
        
        # Check in models directory
        models_dir = Path(settings.models_dir)
        if models_dir.exists():
            # Try exact filename match
            model_path = models_dir / model
            if model_path.exists():
                return model_path
            
            # Try adding .gguf extension
            if not model.lower().endswith(".gguf"):
                model_path = models_dir / f"{model}.gguf"
                if model_path.exists():
                    return model_path
            
            # Search for partial match
            for gguf_file in models_dir.glob("*.gguf"):
                if model.lower() in gguf_file.name.lower():
                    return gguf_file
        
        return None

    async def load_model(
        self,
        model: str,
        chat_format: Optional[str] = None,
        n_ctx: Optional[int] = None,
        n_gpu_layers: Optional[int] = None,
        **kwargs,
    ) -> Llama:
        """Load a model, using cache if available.
        
        Args:
            model: Model identifier (filename or path)
            chat_format: Optional chat format override
            n_ctx: Optional context size override
            n_gpu_layers: Optional GPU layers override
            **kwargs: Additional arguments passed to Llama constructor
            
        Returns:
            Loaded Llama model instance
            
        Raises:
            FileNotFoundError: If model file not found
            RuntimeError: If model loading fails
        """
        # Resolve model path
        model_path = self._resolve_model_path(model)
        if model_path is None:
            raise FileNotFoundError(f"Model not found: {model}")

        model_id = self._get_model_id(model_path)
        
        # Check if already loaded
        if model_id in self._models:
            # Move to end (most recently used)
            self._models.move_to_end(model_id)
            return self._models[model_id]

        # Get or create loading lock for this model
        async with self._global_lock:
            if model_id not in self._loading_locks:
                self._loading_locks[model_id] = asyncio.Lock()
            load_lock = self._loading_locks[model_id]

        # Load with per-model lock to prevent duplicate loads
        async with load_lock:
            # Check again after acquiring lock
            if model_id in self._models:
                self._models.move_to_end(model_id)
                return self._models[model_id]

            # Ensure we have room
            await self._ensure_capacity()

            # Load the model
            llm = await self._load_model_internal(
                model_path=model_path,
                chat_format=chat_format,
                n_ctx=n_ctx,
                n_gpu_layers=n_gpu_layers,
                **kwargs,
            )

            # Store in cache
            self._models[model_id] = llm
            
            return llm

    async def _load_model_internal(
        self,
        model_path: Path,
        chat_format: Optional[str] = None,
        n_ctx: Optional[int] = None,
        n_gpu_layers: Optional[int] = None,
        **kwargs,
    ) -> Llama:
        """Internal method to load a model.
        
        Args:
            model_path: Path to the model file
            chat_format: Optional chat format
            n_ctx: Optional context size
            n_gpu_layers: Optional GPU layers
            **kwargs: Additional Llama constructor arguments
            
        Returns:
            Loaded Llama instance
        """
        settings = get_settings()
        model_id = self._get_model_id(model_path)

        # Determine chat format
        if chat_format is None:
            chat_format = detect_chat_format_from_filename(model_path.name)

        # Determine context size
        if n_ctx is None:
            n_ctx = settings.default_context_size

        # Determine GPU layers
        if n_gpu_layers is None:
            n_gpu_layers = settings.default_n_gpu_layers
            # Check if GPU is available
            gpu_available, _ = detect_gpu_support()
            if not gpu_available:
                n_gpu_layers = 0

        # Check for multimodal
        multimodal_type = detect_multimodal_model(model_path.name)
        chat_handler = None
        
        if multimodal_type:
            # Import multimodal handlers
            chat_handler = self._get_multimodal_handler(multimodal_type, model_path)

        # Build Llama kwargs
        llama_kwargs = {
            "model_path": str(model_path),
            "n_ctx": n_ctx,
            "n_gpu_layers": n_gpu_layers,
            "verbose": False,
        }
        
        if chat_format:
            llama_kwargs["chat_format"] = chat_format
        
        if chat_handler:
            llama_kwargs["chat_handler"] = chat_handler

        # Add any extra kwargs
        llama_kwargs.update(kwargs)

        # Load model in thread pool to not block event loop
        loop = asyncio.get_event_loop()
        llm = await loop.run_in_executor(None, lambda: Llama(**llama_kwargs))

        # Store metadata
        self._metadata[model_id] = ModelMetadata(
            model_id=model_id,
            path=model_path,
            chat_format=chat_format,
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            is_multimodal=multimodal_type is not None,
            multimodal_type=multimodal_type,
            size_bytes=model_path.stat().st_size,
        )

        return llm

    def _get_multimodal_handler(self, multimodal_type: str, model_path: Path) -> Optional[Any]:
        """Get the appropriate multimodal chat handler.
        
        Args:
            multimodal_type: Type of multimodal model
            model_path: Path to the model file
            
        Returns:
            Chat handler instance or None
        """
        try:
            from llama_cpp.llama_chat_format import (
                Llava15ChatHandler,
                Llava16ChatHandler,
                MoondreamChatHandler,
            )

            # Look for clip/mmproj file in same directory
            model_dir = model_path.parent
            clip_patterns = ["*mmproj*", "*clip*", "*vision*"]
            clip_path = None
            
            for pattern in clip_patterns:
                matches = list(model_dir.glob(pattern))
                if matches:
                    clip_path = matches[0]
                    break

            if clip_path is None:
                # Cannot load multimodal without clip model
                return None

            if multimodal_type == "llava-1-5":
                return Llava15ChatHandler(clip_model_path=str(clip_path))
            elif multimodal_type == "llava-1-6":
                return Llava16ChatHandler(clip_model_path=str(clip_path))
            elif multimodal_type == "moondream2":
                return MoondreamChatHandler(clip_model_path=str(clip_path))
            
            return None
        except ImportError:
            return None

    async def _ensure_capacity(self) -> None:
        """Ensure there's capacity for a new model by unloading LRU if needed."""
        settings = get_settings()
        
        while len(self._models) >= settings.max_loaded_models:
            # Remove least recently used (first item in OrderedDict)
            if self._models:
                oldest_id, oldest_model = self._models.popitem(last=False)
                
                # Cleanup
                del oldest_model
                if oldest_id in self._metadata:
                    del self._metadata[oldest_id]

    async def unload_model(self, model: str) -> bool:
        """Unload a model from memory.
        
        Args:
            model: Model identifier
            
        Returns:
            True if model was unloaded, False if not found
        """
        model_path = self._resolve_model_path(model)
        if model_path is None:
            return False

        model_id = self._get_model_id(model_path)
        
        async with self._global_lock:
            if model_id in self._models:
                del self._models[model_id]
                if model_id in self._metadata:
                    del self._metadata[model_id]
                return True
        
        return False

    def get_model(self, model: str) -> Optional[Llama]:
        """Get a loaded model without loading it.
        
        Args:
            model: Model identifier
            
        Returns:
            Llama instance or None if not loaded
        """
        model_path = self._resolve_model_path(model)
        if model_path is None:
            return None

        model_id = self._get_model_id(model_path)
        return self._models.get(model_id)

    def is_loaded(self, model: str) -> bool:
        """Check if a model is loaded.
        
        Args:
            model: Model identifier
            
        Returns:
            True if model is loaded
        """
        return self.get_model(model) is not None

    def get_metadata(self, model: str) -> Optional[ModelMetadata]:
        """Get metadata for a loaded model.
        
        Args:
            model: Model identifier
            
        Returns:
            ModelMetadata or None if not loaded
        """
        model_path = self._resolve_model_path(model)
        if model_path is None:
            return None

        model_id = self._get_model_id(model_path)
        return self._metadata.get(model_id)

    def list_loaded_models(self) -> List[ModelMetadata]:
        """Get list of all loaded models.
        
        Returns:
            List of ModelMetadata for loaded models
        """
        return list(self._metadata.values())

    async def list_available_models(self) -> List[Dict[str, Any]]:
        """List all available GGUF models in the models directory.
        
        Returns:
            List of model info dictionaries
        """
        settings = get_settings()
        models_dir = Path(settings.models_dir)
        
        if not models_dir.exists():
            return []

        models = []
        for gguf_file in models_dir.glob("*.gguf"):
            if gguf_file.is_file():
                stat = gguf_file.stat()
                model_id = gguf_file.name
                models.append({
                    "id": model_id,
                    "path": str(gguf_file),
                    "size_bytes": stat.st_size,
                    "created": int(stat.st_mtime),
                    "loaded": model_id in self._models,
                })
        
        return models

    async def unload_all(self) -> int:
        """Unload all models.
        
        Returns:
            Number of models unloaded
        """
        async with self._global_lock:
            count = len(self._models)
            self._models.clear()
            self._metadata.clear()
            return count


# Global model manager instance
model_manager = ModelManager()
