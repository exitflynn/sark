"""
Universal Model Loader - Handles ONNX and CoreML models transparently.
Auto-detects model format and creates appropriate inference engine.
"""

import os
import tempfile
import urllib.request
import urllib.parse
from typing import Optional, Any, Tuple
import numpy as np
import logging

from core.model_format import (
    ModelFormat, ModelFormatDetector, InferenceFactory, ModelFormatInfo
)

logger = logging.getLogger(__name__)


class UniversalModelLoader:
    """
    Universal model loader supporting multiple formats.
    
    Automatically detects model format and creates appropriate inference engine.
    Provides unified interface for ONNX, CoreML, and other formats.
    """
    
    def __init__(self, compute_unit: str = 'CPU', format_hint: Optional[ModelFormat] = None):
        """
        Initialize universal model loader.
        
        Args:
            compute_unit: Compute unit to use ('CPU', 'GPU', 'NEURAL_ENGINE', etc.)
            format_hint: Optional hint about model format (auto-detect if None)
        """
        self.compute_unit = compute_unit
        self.format_hint = format_hint
        self.engine = None
        self.model_format: Optional[ModelFormat] = None
        self.model_path: Optional[str] = None
        self._register_default_engines()
    
    @staticmethod
    def _register_default_engines():
        """Register default inference engines."""
        try:
            from core.coreml_engine import CoreMLInferenceEngine
            InferenceFactory.register_engine(ModelFormat.COREML, CoreMLInferenceEngine)
            logger.info("✅ CoreML engine registered")
        except Exception as e:
            logger.debug(f"CoreML engine not available: {e}")
        
        try:
            from worker.legacy.model_loader import ModelLoader as ONNXModelLoader
            # Wrap ONNX loader to match interface
            InferenceFactory.register_engine(ModelFormat.ONNX, ONNXModelLoader)
            logger.info("✅ ONNX engine registered")
        except Exception as e:
            logger.debug(f"ONNX engine not available: {e}")
    
    def download_model(self, model_url: str, download_dir: Optional[str] = None) -> str:
        """
        Download model from URL or use local file path.
        
        Args:
            model_url: URL to download the model from, or local file path
            download_dir: Directory to save the model (default: temp directory)
            
        Returns:
            Path to model file
        """
        # Check if it's a local file path
        if os.path.exists(model_url):
            logger.info(f"Using local model file: {model_url}")
            self.model_format = ModelFormatDetector.detect(model_url)
            return model_url
        
        # Otherwise, treat as URL and download
        if download_dir is None:
            download_dir = tempfile.gettempdir()
        
        # Detect format from URL
        self.model_format = ModelFormatDetector.from_url(model_url)
        
        # Parse URL to get filename
        parsed_url = urllib.parse.urlparse(model_url)
        filename = os.path.basename(parsed_url.path)
        if not filename:
            filename = f'model.{self.model_format.value}'
        
        model_path = os.path.join(download_dir, filename)
        
        # Download the model
        logger.info(f"Downloading model from {model_url}...")
        try:
            urllib.request.urlretrieve(model_url, model_path)
            logger.info(f"✅ Model downloaded to {model_path}")
        except Exception as e:
            logger.error(f"❌ Failed to download model: {e}")
            raise
        
        return model_path
    
    def load(self, model_path: str):
        """
        Load model (auto-detect format).
        
        Args:
            model_path: Path to model file
            
        Raises:
            FileNotFoundError: If model file not found
            ValueError: If format not supported or engine not available
        """
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")
        
        self.model_path = model_path
        
        # Detect format if not already known
        if self.model_format is None:
            if self.format_hint:
                self.model_format = self.format_hint
            else:
                self.model_format = ModelFormatDetector.detect(model_path)
        
        logger.info(f"Loading {self.model_format.value} model: {model_path}")
        
        # Check format is supported
        if not ModelFormatInfo.is_supported(self.model_format):
            raise ValueError(f"Unsupported model format: {self.model_format.value}")
        
        # Check dependencies
        available, missing = ModelFormatInfo.check_dependencies(self.model_format)
        if not available:
            raise RuntimeError(
                f"Missing dependencies for {self.model_format.value}: {', '.join(missing)}\n"
                f"Install with: pip install {' '.join(missing)}"
            )
        
        # Create appropriate engine
        try:
            self.engine = InferenceFactory.create_engine(
                self.model_format,
                compute_unit=self.compute_unit
            )
        except ValueError as e:
            raise RuntimeError(f"Engine not available for {self.model_format.value}: {e}")
        
        # Load model with engine
        try:
            if hasattr(self.engine, 'load'):
                self.engine.load(model_path)
            elif hasattr(self.engine, 'load_model'):
                self.engine.load_model(model_path)
            else:
                raise RuntimeError(f"Engine doesn't support load method")
            
            logger.info(f"✅ Model loaded successfully ({self.model_format.value})")
        
        except Exception as e:
            logger.error(f"❌ Failed to load model: {e}")
            raise
    
    def get_input_shape(self) -> Optional[Tuple]:
        """Get input shape from model."""
        if self.engine is None:
            return None
        
        if hasattr(self.engine, 'get_input_shape'):
            return self.engine.get_input_shape()
        elif hasattr(self.engine, '_get_input_shape'):
            return self.engine._get_input_shape()
        
        return None
    
    def create_sample_input(self) -> np.ndarray:
        """Create sample input for inference."""
        if self.engine is None:
            raise RuntimeError("Model not loaded")
        
        if hasattr(self.engine, 'create_sample_input'):
            sample = self.engine.create_sample_input()
            if sample is not None:
                return sample
        elif hasattr(self.engine, 'create_input'):
            return self.engine.create_input()
        
        # Fallback: create random input
        shape = self.get_input_shape()
        if shape is None:
            raise RuntimeError("Could not determine input shape")
        
        return np.random.rand(*shape).astype(np.float32)
    
    def run_inference(self, input_data: np.ndarray) -> Any:
        """Run inference."""
        if self.engine is None:
            raise RuntimeError("Model not loaded. Call load() first.")
        
        # Try different interface names
        if hasattr(self.engine, 'run_inference'):
            return self.engine.run_inference(input_data)
        elif hasattr(self.engine, 'predict'):
            return self.engine.predict(input_data)
        else:
            raise RuntimeError(f"Engine doesn't support inference")
    
    def get_model_info(self) -> dict:
        """Get information about loaded model."""
        return {
            'format': self.model_format.value if self.model_format else None,
            'path': self.model_path,
            'compute_unit': self.compute_unit,
            'input_shape': self.get_input_shape(),
            'engine': self.engine.__class__.__name__ if self.engine else None,
        }
    
    def cleanup(self):
        """Cleanup resources."""
        if self.engine and hasattr(self.engine, 'cleanup'):
            self.engine.cleanup()
        
        self.engine = None
        self.model_path = None
        logger.info("✅ Model cleaned up")
    
    @staticmethod
    def get_supported_formats() -> dict:
        """Get supported model formats and their info."""
        formats = {}
        for fmt in ModelFormatInfo.get_supported_formats():
            formats[fmt.value] = ModelFormatInfo.get_info(fmt)
        return formats
    
    @staticmethod
    def print_supported_formats():
        """Print supported model formats."""
        ModelFormatInfo.print_supported_formats()

