"""
CoreML Support Tests - Tests for multi-format model loading.
Tests ONNX, CoreML, and universal model loader.
"""

import unittest
import tempfile
import os
from core.model_format import (
    ModelFormat, ModelFormatDetector, ModelFormatInfo, InferenceFactory
)
from core.universal_model_loader import UniversalModelLoader


class TestModelFormatDetection(unittest.TestCase):
    """Test model format detection."""
    
    def test_detect_onnx(self):
        """Test ONNX format detection."""
        fmt = ModelFormatDetector.detect('/path/to/model.onnx')
        self.assertEqual(fmt, ModelFormat.ONNX)
    
    def test_detect_coreml(self):
        """Test CoreML format detection."""
        fmt = ModelFormatDetector.detect('/path/to/model.mlmodel')
        self.assertEqual(fmt, ModelFormat.COREML)
    
    def test_detect_pytorch(self):
        """Test PyTorch format detection."""
        fmt1 = ModelFormatDetector.detect('/path/to/model.pt')
        fmt2 = ModelFormatDetector.detect('/path/to/model.pth')
        self.assertEqual(fmt1, ModelFormat.PYTORCH)
        self.assertEqual(fmt2, ModelFormat.PYTORCH)
    
    def test_detect_tensorflow(self):
        """Test TensorFlow format detection."""
        fmt1 = ModelFormatDetector.detect('/path/to/model.pb')
        fmt2 = ModelFormatDetector.detect('/path/to/model.h5')
        self.assertEqual(fmt1, ModelFormat.TENSORFLOW)
        self.assertEqual(fmt2, ModelFormat.TENSORFLOW)
    
    def test_detect_unknown(self):
        """Test unknown format detection."""
        fmt = ModelFormatDetector.detect('/path/to/model.xyz')
        self.assertEqual(fmt, ModelFormat.UNKNOWN)
    
    def test_from_url_onnx(self):
        """Test format detection from URL."""
        fmt = ModelFormatDetector.from_url(
            'https://example.com/models/model.onnx'
        )
        self.assertEqual(fmt, ModelFormat.ONNX)
    
    def test_from_url_coreml(self):
        """Test CoreML format detection from URL."""
        fmt = ModelFormatDetector.from_url(
            'https://example.com/models/image_classifier.mlmodel'
        )
        self.assertEqual(fmt, ModelFormat.COREML)


class TestModelFormatInfo(unittest.TestCase):
    """Test model format information."""
    
    def test_get_onnx_info(self):
        """Test getting ONNX format info."""
        info = ModelFormatInfo.get_info(ModelFormat.ONNX)
        self.assertIn('name', info)
        self.assertIn('extensions', info)
        self.assertIn('platforms', info)
        self.assertEqual(info['name'], 'ONNX Runtime')
    
    def test_get_coreml_info(self):
        """Test getting CoreML format info."""
        info = ModelFormatInfo.get_info(ModelFormat.COREML)
        self.assertEqual(info['name'], 'CoreML')
        self.assertIn('.mlmodel', info['extensions'])
        self.assertIn('macOS', info['platforms'])
    
    def test_supported_formats(self):
        """Test getting supported formats list."""
        formats = ModelFormatInfo.get_supported_formats()
        self.assertIn(ModelFormat.ONNX, formats)
        self.assertIn(ModelFormat.COREML, formats)
        self.assertNotIn(ModelFormat.UNKNOWN, formats)
    
    def test_is_supported(self):
        """Test format support check."""
        self.assertTrue(ModelFormatInfo.is_supported(ModelFormat.ONNX))
        self.assertTrue(ModelFormatInfo.is_supported(ModelFormat.COREML))
        self.assertFalse(ModelFormatInfo.is_supported(ModelFormat.UNKNOWN))
    
    def test_check_onnx_dependencies(self):
        """Test ONNX dependency check."""
        available, missing = ModelFormatInfo.check_dependencies(ModelFormat.ONNX)
        # ONNX should be available (required by tests)
        self.assertTrue(available or 'onnxruntime' in missing)
    
    def test_check_coreml_dependencies(self):
        """Test CoreML dependency check."""
        available, missing = ModelFormatInfo.check_dependencies(ModelFormat.COREML)
        # May or may not be available depending on environment
        if not available:
            self.assertIn('coremltools', missing)


class TestInferenceFactory(unittest.TestCase):
    """Test inference engine factory."""
    
    def setUp(self):
        """Set up factory for tests."""
        # Register engines
        UniversalModelLoader._register_default_engines()
    
    def test_get_available_formats(self):
        """Test getting available engine formats."""
        formats = InferenceFactory.get_available_formats()
        # At least ONNX should be available
        self.assertGreater(len(formats), 0)
    
    def test_create_onnx_engine(self):
        """Test creating ONNX inference engine."""
        if ModelFormat.ONNX in InferenceFactory.get_available_formats():
            engine = InferenceFactory.create_engine(ModelFormat.ONNX)
            self.assertIsNotNone(engine)
    
    def test_create_coreml_engine(self):
        """Test creating CoreML inference engine."""
        if ModelFormat.COREML in InferenceFactory.get_available_formats():
            engine = InferenceFactory.create_engine(ModelFormat.COREML)
            self.assertIsNotNone(engine)
    
    def test_create_unsupported_format(self):
        """Test creating engine for unsupported format."""
        with self.assertRaises(ValueError):
            InferenceFactory.create_engine(ModelFormat.UNKNOWN)


class TestUniversalModelLoader(unittest.TestCase):
    """Test universal model loader."""
    
    def setUp(self):
        """Set up loader for tests."""
        self.loader = UniversalModelLoader(compute_unit='CPU')
    
    def test_initialization(self):
        """Test loader initialization."""
        self.assertEqual(self.loader.compute_unit, 'CPU')
        self.assertIsNone(self.loader.model_format)
        self.assertIsNone(self.loader.engine)
    
    def test_format_detection_onnx(self):
        """Test format detection during download check."""
        # Create a temporary ONNX file
        with tempfile.NamedTemporaryFile(suffix='.onnx', delete=False) as f:
            temp_path = f.name
        
        try:
            # This should detect ONNX format
            result = self.loader.download_model(temp_path)
            self.assertEqual(result, temp_path)
            self.assertEqual(self.loader.model_format, ModelFormat.ONNX)
        finally:
            os.unlink(temp_path)
    
    def test_format_detection_coreml(self):
        """Test CoreML format detection."""
        with tempfile.NamedTemporaryFile(suffix='.mlmodel', delete=False) as f:
            temp_path = f.name
        
        try:
            result = self.loader.download_model(temp_path)
            self.assertEqual(result, temp_path)
            self.assertEqual(self.loader.model_format, ModelFormat.COREML)
        finally:
            os.unlink(temp_path)
    
    def test_format_hint(self):
        """Test providing format hint."""
        loader = UniversalModelLoader(
            compute_unit='CPU',
            format_hint=ModelFormat.COREML
        )
        self.assertEqual(loader.format_hint, ModelFormat.COREML)
    
    def test_load_nonexistent_model(self):
        """Test loading nonexistent model."""
        with self.assertRaises(FileNotFoundError):
            self.loader.load('/nonexistent/model.onnx')
    
    def test_get_supported_formats(self):
        """Test getting supported formats list."""
        formats = UniversalModelLoader.get_supported_formats()
        self.assertIsInstance(formats, dict)
        self.assertIn('onnx', formats)
        self.assertIn('coreml', formats)
    
    def test_get_model_info_unloaded(self):
        """Test getting info from unloaded model."""
        info = self.loader.get_model_info()
        self.assertIsNone(info['format'])
        self.assertIsNone(info['path'])


class TestMultiFormatSupport(unittest.TestCase):
    """Test multi-format model support."""
    
    def test_format_enum_values(self):
        """Test ModelFormat enum values."""
        self.assertEqual(ModelFormat.ONNX.value, 'onnx')
        self.assertEqual(ModelFormat.COREML.value, 'coreml')
        self.assertEqual(ModelFormat.PYTORCH.value, 'pytorch')
        self.assertEqual(ModelFormat.TENSORFLOW.value, 'tensorflow')
    
    def test_all_extensions_mapped(self):
        """Test all file extensions are mapped."""
        detector = ModelFormatDetector()
        extensions = detector.EXTENSIONS
        
        # Check common extensions
        self.assertIn('.onnx', extensions)
        self.assertIn('.mlmodel', extensions)
        self.assertIn('.pt', extensions)
        self.assertIn('.pth', extensions)
    
    def test_format_info_completeness(self):
        """Test format info has all required fields."""
        required_fields = ['name', 'extensions', 'description', 'platforms']
        
        for fmt in ModelFormatInfo.get_supported_formats():
            info = ModelFormatInfo.get_info(fmt)
            for field in required_fields:
                self.assertIn(field, info, f"Missing {field} for {fmt.value}")
    
    def test_case_insensitive_detection(self):
        """Test case-insensitive format detection."""
        fmt1 = ModelFormatDetector.detect('model.ONNX')
        fmt2 = ModelFormatDetector.detect('model.onnx')
        self.assertEqual(fmt1, fmt2)
        self.assertEqual(fmt1, ModelFormat.ONNX)


class TestCoreMLEngine(unittest.TestCase):
    """Test CoreML engine features."""
    
    def test_coreml_compute_units(self):
        """Test available CoreML compute units."""
        try:
            from core.coreml_engine import CoreMLInferenceEngine
            
            engine = CoreMLInferenceEngine()
            units = engine.get_compute_units()
            
            # CPU should always be available
            self.assertIn('CPU', units)
        
        except ImportError:
            self.skipTest("CoreML not available")
    
    def test_coreml_engine_cleanup(self):
        """Test CoreML engine cleanup."""
        try:
            from core.coreml_engine import CoreMLInferenceEngine
            
            engine = CoreMLInferenceEngine()
            engine.cleanup()
            
            # After cleanup, model should be None
            self.assertIsNone(engine.model)
            self.assertIsNone(engine.model_path)
        
        except ImportError:
            self.skipTest("CoreML not available")


if __name__ == '__main__':
    unittest.main()

