"""
Model Format Support - Handles multiple ML model formats.
Supports ONNX, CoreML, and provides extensible interface for other formats.
"""

from enum import Enum
from typing import Optional, Dict, Any, Tuple
import os
import logging


logger = logging.getLogger(__name__)


class ModelFormat(Enum):
    """Supported model formats."""
    ONNX = "onnx"
    COREML = "coreml"
    PYTORCH = "pytorch"
    TENSORFLOW = "tensorflow"
    UNKNOWN = "unknown"


class ModelFormatDetector:
    """Detects model format from file path or URL."""
    
    EXTENSIONS = {
        '.onnx': ModelFormat.ONNX,
        '.mlmodel': ModelFormat.COREML,
        '.pt': ModelFormat.PYTORCH,
        '.pth': ModelFormat.PYTORCH,
        '.pb': ModelFormat.TENSORFLOW,
        '.h5': ModelFormat.TENSORFLOW,
        '.savedmodel': ModelFormat.TENSORFLOW,
    }
    
    @staticmethod
    def detect(model_path: str) -> ModelFormat:
        """
        Detect model format from file path.
        
        Args:
            model_path: Path to model file
            
        Returns:
            Detected ModelFormat
        """
        # Get extension
        _, ext = os.path.splitext(model_path.lower())
        
        detected = ModelFormatDetector.EXTENSIONS.get(ext, ModelFormat.UNKNOWN)
        logger.info(f"Detected format {detected.value} for model: {model_path}")
        
        return detected
    
    @staticmethod
    def from_url(url: str) -> ModelFormat:
        """
        Detect model format from URL.
        
        Args:
            url: URL to model file
            
        Returns:
            Detected ModelFormat
        """
        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        path = parsed.path
        return ModelFormatDetector.detect(path)


class ModelFormatInfo:
    """Information about supported model formats."""
    
    INFO = {
        ModelFormat.ONNX: {
            'name': 'ONNX Runtime',
            'extensions': ['.onnx'],
            'description': 'ONNX format - cross-platform, hardware-agnostic',
            'requires': ['onnxruntime'],
            'providers': ['CPU', 'CUDA', 'DML', 'OpenVINO', 'CoreML'],
            'platforms': ['Windows', 'Linux', 'macOS', 'iOS', 'Android'],
        },
        ModelFormat.COREML: {
            'name': 'CoreML',
            'extensions': ['.mlmodel'],
            'description': 'Apple CoreML format - optimized for Apple devices',
            'requires': ['coremltools'],
            'providers': ['CPU', 'Neural Engine', 'GPU'],
            'platforms': ['macOS', 'iOS', 'iPadOS', 'watchOS'],
        },
        ModelFormat.PYTORCH: {
            'name': 'PyTorch',
            'extensions': ['.pt', '.pth'],
            'description': 'PyTorch saved model format',
            'requires': ['torch'],
            'providers': ['CPU', 'CUDA'],
            'platforms': ['Windows', 'Linux', 'macOS'],
        },
        ModelFormat.TENSORFLOW: {
            'name': 'TensorFlow',
            'extensions': ['.pb', '.h5', '.savedmodel'],
            'description': 'TensorFlow saved model format',
            'requires': ['tensorflow'],
            'providers': ['CPU', 'CUDA', 'TPU'],
            'platforms': ['Windows', 'Linux', 'macOS', 'Raspberry Pi'],
        },
    }
    
    @staticmethod
    def get_info(model_format: ModelFormat) -> Dict[str, Any]:
        """
        Get information about a model format.
        
        Args:
            model_format: ModelFormat enum value
            
        Returns:
            Dictionary with format information
        """
        return ModelFormatInfo.INFO.get(model_format, {})
    
    @staticmethod
    def get_supported_formats() -> list:
        """Get list of supported formats."""
        return [fmt for fmt in ModelFormat if fmt != ModelFormat.UNKNOWN]
    
    @staticmethod
    def is_supported(model_format: ModelFormat) -> bool:
        """Check if format is supported."""
        return model_format in ModelFormatInfo.INFO
    
    @staticmethod
    def check_dependencies(model_format: ModelFormat) -> Tuple[bool, list]:
        """
        Check if dependencies for a format are installed.
        
        Args:
            model_format: ModelFormat to check
            
        Returns:
            (all_installed: bool, missing_packages: list)
        """
        info = ModelFormatInfo.get_info(model_format)
        required = info.get('requires', [])
        missing = []
        
        for package in required:
            try:
                __import__(package)
            except ImportError:
                missing.append(package)
        
        return len(missing) == 0, missing
    
    @staticmethod
    def print_supported_formats():
        """Print supported model formats."""
        print("\n" + "="*70)
        print("SUPPORTED MODEL FORMATS")
        print("="*70)
        
        for fmt in ModelFormatInfo.get_supported_formats():
            info = ModelFormatInfo.get_info(fmt)
            print(f"\n{info['name']} ({fmt.value})")
            print(f"  Extensions: {', '.join(info['extensions'])}")
            print(f"  Description: {info['description']}")
            print(f"  Platforms: {', '.join(info['platforms'])}")
            print(f"  Providers: {', '.join(info['providers'])}")
            
            installed, missing = ModelFormatInfo.check_dependencies(fmt)
            status = "✅ INSTALLED" if installed else f"❌ MISSING: {', '.join(missing)}"
            print(f"  Status: {status}")
        
        print("\n" + "="*70 + "\n")


class InferenceFactory:
    """Factory for creating inference engines based on model format."""
    
    _engines: Dict[ModelFormat, Any] = {}
    
    @staticmethod
    def register_engine(model_format: ModelFormat, engine_class):
        """
        Register an inference engine for a format.
        
        Args:
            model_format: ModelFormat to register
            engine_class: Engine class (should have load and run_inference methods)
        """
        InferenceFactory._engines[model_format] = engine_class
        logger.info(f"Registered engine for {model_format.value}: {engine_class.__name__}")
    
    @staticmethod
    def create_engine(model_format: ModelFormat, **kwargs):
        """
        Create an inference engine for a model format.
        
        Args:
            model_format: ModelFormat to create engine for
            **kwargs: Additional arguments for engine
            
        Returns:
            Engine instance
            
        Raises:
            ValueError: If format not supported or engine not registered
        """
        if model_format not in InferenceFactory._engines:
            raise ValueError(
                f"No engine registered for format: {model_format.value}. "
                f"Supported: {list(InferenceFactory._engines.keys())}"
            )
        
        engine_class = InferenceFactory._engines[model_format]
        engine = engine_class(**kwargs)
        logger.info(f"Created inference engine for {model_format.value}")
        
        return engine
    
    @staticmethod
    def get_available_formats() -> list:
        """Get list of formats with registered engines."""
        return list(InferenceFactory._engines.keys())


class BaseInferenceEngine:
    """Base class for inference engines."""
    
    def __init__(self, compute_unit: str = 'CPU'):
        """
        Initialize inference engine.
        
        Args:
            compute_unit: Compute unit to use
        """
        self.compute_unit = compute_unit
        self.session = None
        self.model_path: Optional[str] = None
    
    def load(self, model_path: str):
        """Load model. Must be implemented by subclass."""
        raise NotImplementedError()
    
    def run_inference(self, input_data):
        """Run inference. Must be implemented by subclass."""
        raise NotImplementedError()
    
    def cleanup(self):
        """Cleanup resources. Can be overridden by subclass."""
        self.session = None
        self.model_path = None

