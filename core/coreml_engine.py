"""
CoreML Inference Engine - Executes CoreML models on Apple devices.
Provides efficient inference on macOS, iOS, and other Apple platforms.
"""

import logging
from typing import Optional, Any, Tuple
import numpy as np

logger = logging.getLogger(__name__)


class CoreMLInferenceEngine:
    """Inference engine for CoreML models."""
    
    def __init__(self, compute_unit: str = 'CPU'):
        """
        Initialize CoreML inference engine.
        
        Args:
            compute_unit: Compute unit to use:
                - 'CPU': CPU inference
                - 'GPU': GPU inference  (if available)
                - 'NEURAL_ENGINE': Neural Engine (if available on device)
                - 'ALL': Use all available (default)
        """
        self.compute_unit = compute_unit
        self.model = None
        self.model_path: Optional[str] = None
        self._check_coreml_available()
    
    @staticmethod
    def _check_coreml_available() -> bool:
        try:
            import coremltools
            import platform
            
            system = platform.system()
            if system not in ['Darwin']:  # Darwin is macOS
                logger.warning(f"CoreML is not fully supported on {system}. ")
            
            logger.info(f"CoreML available: {coremltools.__version__}")
            return True
        
        except ImportError:
            logger.warning("CoreML not available. Install with: pip install coremltools")
            return False
    
    def load(self, model_path: str):
        import os
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")
        
        if not model_path.endswith('.mlmodel'):
            logger.warning(f"Expected .mlmodel file, got: {model_path}")
        
        try:
            import coremltools as ct
            
            logger.info(f"Loading CoreML model: {model_path}")
            self.model = ct.models.MLModel(model_path)
            self.model_path = model_path
            
            self._log_model_info()
            
        except Exception as e:
            raise RuntimeError(f"Failed to load CoreML model: {e}")
    
    def _log_model_info(self):
        """Log information about loaded model."""
        if not self.model:
            return
        
        logger.info(f"Model loaded successfully")
        logger.info(f"Model type: {type(self.model)}")
        
        try:
            if hasattr(self.model, 'input_description'):
                logger.info(f"Inputs: {self.model.input_description}")
            if hasattr(self.model, 'output_description'):
                logger.info(f"Outputs: {self.model.output_description}")
        except Exception as e:
            logger.debug(f"Could not get model I/O info: {e}")
    
    def get_input_shape(self) -> Optional[Tuple]:
        if not self.model:
            return None
        
        try:
            spec = self.model.spec
            
            if spec and spec.description:
                input_desc = spec.description.input
                if input_desc:
                    first_input = input_desc[0]
                    
                    if hasattr(first_input, 'type'):
                        input_type = first_input.type
                        
                        if hasattr(input_type, 'multiArrayType'):
                            shape = tuple(input_type.multiArrayType.shape)
                            logger.debug(f"Input shape: {shape}")
                            return shape
                        
                        elif hasattr(input_type, 'imageType'):

                            img_type = input_type.imageType
                            if img_type:
                                height = img_type.height
                                width = img_type.width
                                return (1, 3, height, width)  # BCHW format
        
        except Exception as e:
            logger.debug(f"Could not determine input shape: {e}")
        
        return None
    
    def create_sample_input(self) -> Optional[np.ndarray]:
        shape = self.get_input_shape()
        
        if shape is None:
            logger.warning("Could not determine input shape")
            return None
        
        try:
            sample_input = np.random.rand(*shape).astype(np.float32)
            return sample_input
        
        except Exception as e:
            logger.error(f"Failed to create sample input: {e}")
            return None
    
    def run_inference(self, input_data: np.ndarray) -> Any:
        if not self.model:
            raise RuntimeError("Model not loaded. Call load() first.")
        
        try:
            if isinstance(input_data, np.ndarray):
                output = self._run_with_array_input(input_data)
            elif isinstance(input_data, dict):
                output = self.model.predict(input_data)
            else:
                raise ValueError(f"Unsupported input type: {type(input_data)}")
            
            return output
        
        except Exception as e:
            raise RuntimeError(f"Inference failed: {e}")
    
    def _run_with_array_input(self, input_data: np.ndarray) -> Any:
        import coremltools.models.datatypes as datatypes
        
        spec = self.model.spec
        if not spec or not spec.description:
            raise RuntimeError("Cannot determine input format from model")
        
        input_desc = spec.description.input[0]
        input_name = input_desc.name
        
        input_dict = {}
        
        if hasattr(input_desc.type, 'multiArrayType'):
            # Multi-array (tensor) input
            input_dict[input_name] = input_data
        
        elif hasattr(input_desc.type, 'imageType'):
            from PIL import Image
            
            if input_data.dtype != np.uint8:
                input_data = (input_data * 255).astype(np.uint8)
            
            if len(input_data.shape) == 3:
                img = Image.fromarray(input_data)
            else:
                # handling for grayscale or other formats
                img = Image.fromarray(input_data[0] if len(input_data.shape) == 4 else input_data)
            
            input_dict[input_name] = img
        
        else:
            # Default: just pass the array
            input_dict[input_name] = input_data
        
        # Run prediction
        output = self.model.predict(input_dict)
        return output
    
    def get_compute_units(self) -> list:
        """
        Get available compute units.
        
        Returns:
            List of available compute unit names
        """
        available = ['CPU']
        
        try:
            import platform
            system = platform.system()
            
            if system == 'Darwin':
                available.append('GPU')
                
                import subprocess
                try:
                    result = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'],
                                          capture_output=True, text=True)
                    if 'Apple' in result.stdout or 'M1' in result.stdout or 'M2' in result.stdout:
                        available.append('NEURAL_ENGINE')
                except:
                    pass
        
        except Exception as e:
            logger.debug(f"Could not detect compute units: {e}")
        
        return available
    
    def get_model_size(self) -> Optional[int]:
        if not self.model_path:
            return None
        
        try:
            import os
            return os.path.getsize(self.model_path)
        except:
            return None
    
    def cleanup(self):
        self.model = None
        self.model_path = None
        logger.info("CoreML model cleaned up")

