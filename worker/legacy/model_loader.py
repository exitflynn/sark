"""
Model loading and inference module.
Handles downloading and loading ONNX models for benchmarking.
"""

import os
import tempfile
import urllib.request
import urllib.parse
from typing import Optional, Tuple, Any
import numpy as np
import onnxruntime as ort


class ModelLoader:
    """Handles model downloading and loading for ONNX Runtime."""
    
    def __init__(self, compute_unit: str = 'CPU'):
        """
        Initialize model loader.
        
        Args:
            compute_unit: Compute unit to use ('CPU', 'DML', 'OpenVINO;CPU', etc.)
        """
        self.compute_unit = compute_unit
        self.session: Optional[ort.InferenceSession] = None
        self.model_path: Optional[str] = None
        
    def _get_providers(self) -> list:
        """Get ONNX Runtime providers based on compute unit."""
        providers = []
        
        if self.compute_unit == 'CPU':
            providers = ['CPUExecutionProvider']
        elif self.compute_unit == 'DML':
            providers = ['DmlExecutionProvider', 'CPUExecutionProvider']
        elif self.compute_unit.startswith('OpenVINO'):
            providers = ['OpenVINOExecutionProvider', 'CPUExecutionProvider']
        else:
            providers = ['CPUExecutionProvider']
        
        # Filter to only available providers
        available_providers = ort.get_available_providers()
        return [p for p in providers if p in available_providers]
    
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
            print(f"Using local model file: {model_url}")
            return model_url
        
        # Otherwise, treat as URL and download
        if download_dir is None:
            download_dir = tempfile.gettempdir()
        
        # Parse URL to get filename
        parsed_url = urllib.parse.urlparse(model_url)
        filename = os.path.basename(parsed_url.path)
        if not filename:
            filename = 'model.onnx'
        
        model_path = os.path.join(download_dir, filename)
        
        # Download the model
        print(f"Downloading model from {model_url}...")
        urllib.request.urlretrieve(model_url, model_path)
        print(f"Model downloaded to {model_path}")
        
        return model_path
    
    def load_model(self, model_path: str):
        """
        Load ONNX model into inference session.
        
        Args:
            model_path: Path to ONNX model file
        """
        self.model_path = model_path
        providers = self._get_providers()
        
        print(f"Loading model with providers: {providers}")
        self.session = ort.InferenceSession(
            model_path,
            providers=providers
        )
        
        print(f"Model loaded successfully. Input shape: {self._get_input_shape()}")
    
    def _get_input_shape(self) -> Tuple:
        """Get input shape from model."""
        if self.session is None:
            return None
        
        input_meta = self.session.get_inputs()[0]
        shape = input_meta.shape
        
        # Replace dynamic dimensions with 1
        shape = [s if isinstance(s, int) else 1 for s in shape]
        return tuple(shape)
    
    def create_input(self) -> np.ndarray:
        """
        Create sample input for inference.
        
        Returns:
            NumPy array with appropriate shape and dtype
        """
        if self.session is None:
            raise ValueError("Model not loaded. Call load_model() first.")
        
        input_meta = self.session.get_inputs()[0]
        shape = self._get_input_shape()
        dtype = np.float32  # Default to float32
        
        # Try to get dtype from model
        if hasattr(input_meta, 'type'):
            if 'float' in str(input_meta.type):
                dtype = np.float32
        
        # Create random input (normalized to 0-1 range)
        input_data = np.random.rand(*shape).astype(dtype)
        
        return input_data
    
    def run_inference(self, input_data: np.ndarray) -> Any:
        """
        Run inference on the model.
        
        Args:
            input_data: Input data array
            
        Returns:
            Model output
        """
        if self.session is None:
            raise ValueError("Model not loaded. Call load_model() first.")
        
        input_name = self.session.get_inputs()[0].name
        outputs = self.session.run(None, {input_name: input_data})
        
        return outputs
    
    def cleanup(self):
        """Clean up resources."""
        self.session = None
        if self.model_path and os.path.exists(self.model_path):
            # Optionally delete downloaded model
            # os.remove(self.model_path)
            pass

