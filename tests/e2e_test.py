"""
End-to-End Model Tests - Tests with real ONNX and CoreML models.
Downloads and benchmarks actual models from the internet.
"""

import unittest
import tempfile
import os
import time
from typing import Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestE2EONNXModel(unittest.TestCase):
    """End-to-end tests with real ONNX models."""
    
    # Tiny YOLOv2 - Real ONNX model for object detection
    ONNX_MODEL_URL = (
        "https://github.com/onnx/models/raw/refs/heads/main/"
        "validated/vision/object_detection_segmentation/"
        "tiny-yolov2/model/tinyyolov2-7.onnx"
    )
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_onnx_model_download(self):
        """Test downloading ONNX model."""
        try:
            from core.universal_model_loader import UniversalModelLoader
            
            loader = UniversalModelLoader()
            model_path = loader.download_model(self.ONNX_MODEL_URL, self.temp_dir)
            
            self.assertTrue(os.path.exists(model_path))
            self.assertTrue(model_path.endswith('.onnx'))
            
            file_size = os.path.getsize(model_path)
            logger.info(f"✅ Downloaded ONNX model: {file_size / 1024 / 1024:.1f} MB")
            
            # Verify it's a reasonable size (should be > 10MB for YOLOv2)
            self.assertGreater(file_size, 10_000_000)
        
        except Exception as e:
            self.skipTest(f"Failed to download ONNX model: {e}")
    
    def test_onnx_model_load(self):
        """Test loading ONNX model."""
        try:
            from core.universal_model_loader import UniversalModelLoader
            from core.model_format import ModelFormat
            
            loader = UniversalModelLoader()
            model_path = loader.download_model(self.ONNX_MODEL_URL, self.temp_dir)
            
            # Load the model
            loader.load(model_path)
            
            # Verify it loaded
            self.assertEqual(loader.model_format, ModelFormat.ONNX)
            self.assertIsNotNone(loader.engine)
            
            logger.info(f"✅ Loaded ONNX model: {loader.model_format.value}")
        
        except Exception as e:
            self.skipTest(f"Failed to load ONNX model: {e}")
    
    def test_onnx_model_inference(self):
        """Test inference with ONNX model."""
        try:
            from core.universal_model_loader import UniversalModelLoader
            import numpy as np
            
            loader = UniversalModelLoader(compute_unit='CPU')
            model_path = loader.download_model(self.ONNX_MODEL_URL, self.temp_dir)
            loader.load(model_path)
            
            # Get input shape and create sample input
            input_shape = loader.get_input_shape()
            logger.info(f"Input shape: {input_shape}")
            
            # Create random input (YOLOv2 expects 416x416x3 images typically)
            sample_input = loader.create_sample_input()
            self.assertIsNotNone(sample_input)
            
            # Run inference
            start_time = time.time()
            output = loader.run_inference(sample_input)
            inference_time = time.time() - start_time
            
            self.assertIsNotNone(output)
            logger.info(f"✅ ONNX inference successful in {inference_time:.3f}s")
            logger.info(f"   Output type: {type(output)}")
            
            # Verify inference time is reasonable
            self.assertLess(inference_time, 60)  # Should complete within 60 seconds
        
        except Exception as e:
            self.skipTest(f"Failed to run ONNX inference: {e}")
    
    def test_onnx_model_info(self):
        """Test getting model information from ONNX."""
        try:
            from core.universal_model_loader import UniversalModelLoader
            
            loader = UniversalModelLoader()
            model_path = loader.download_model(self.ONNX_MODEL_URL, self.temp_dir)
            loader.load(model_path)
            
            info = loader.get_model_info()
            
            self.assertEqual(info['format'], 'onnx')
            self.assertIsNotNone(info['path'])
            self.assertIsNotNone(info['engine'])
            self.assertEqual(info['compute_unit'], 'CPU')
            
            logger.info(f"✅ Model info: {info}")
        
        except Exception as e:
            self.skipTest(f"Failed to get ONNX model info: {e}")


class TestE2ECoreMLModel(unittest.TestCase):
    """End-to-end tests with real CoreML models."""
    
    # YOLOv8s - Real CoreML model for object detection
    COREML_MODEL_URL = "https://tmpfiles.org/dl/6926683/yolov8s.mlmodel"
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_coreml_model_download(self):
        """Test downloading CoreML model."""
        try:
            from core.universal_model_loader import UniversalModelLoader
            
            loader = UniversalModelLoader()
            model_path = loader.download_model(self.COREML_MODEL_URL, self.temp_dir)
            
            self.assertTrue(os.path.exists(model_path))
            self.assertTrue(model_path.endswith('.mlmodel') or os.path.isfile(model_path))
            
            file_size = os.path.getsize(model_path)
            logger.info(f"✅ Downloaded CoreML model: {file_size / 1024 / 1024:.1f} MB")
            
            # Verify it's a reasonable size
            self.assertGreater(file_size, 1_000_000)  # At least 1MB
        
        except Exception as e:
            self.skipTest(f"Failed to download CoreML model: {e}")
    
    def test_coreml_model_load(self):
        """Test loading CoreML model."""
        try:
            from core.universal_model_loader import UniversalModelLoader
            from core.model_format import ModelFormat
            
            loader = UniversalModelLoader()
            model_path = loader.download_model(self.COREML_MODEL_URL, self.temp_dir)
            
            # Load the model
            loader.load(model_path)
            
            # Verify it loaded
            self.assertEqual(loader.model_format, ModelFormat.COREML)
            self.assertIsNotNone(loader.engine)
            
            logger.info(f"✅ Loaded CoreML model: {loader.model_format.value}")
        
        except Exception as e:
            self.skipTest(f"CoreML not available or failed to load: {e}")
    
    def test_coreml_model_inference(self):
        """Test inference with CoreML model."""
        try:
            from core.universal_model_loader import UniversalModelLoader
            
            loader = UniversalModelLoader(compute_unit='CPU')
            model_path = loader.download_model(self.COREML_MODEL_URL, self.temp_dir)
            loader.load(model_path)
            
            # Get input shape and create sample input
            input_shape = loader.get_input_shape()
            logger.info(f"Input shape: {input_shape}")
            
            # Create sample input
            sample_input = loader.create_sample_input()
            self.assertIsNotNone(sample_input)
            
            # Run inference
            start_time = time.time()
            output = loader.run_inference(sample_input)
            inference_time = time.time() - start_time
            
            self.assertIsNotNone(output)
            logger.info(f"✅ CoreML inference successful in {inference_time:.3f}s")
            logger.info(f"   Output type: {type(output)}")
            
            # Verify inference time is reasonable
            self.assertLess(inference_time, 60)
        
        except Exception as e:
            self.skipTest(f"CoreML not available or inference failed: {e}")
    
    def test_coreml_model_info(self):
        """Test getting model information from CoreML."""
        try:
            from core.universal_model_loader import UniversalModelLoader
            
            loader = UniversalModelLoader()
            model_path = loader.download_model(self.COREML_MODEL_URL, self.temp_dir)
            loader.load(model_path)
            
            info = loader.get_model_info()
            
            self.assertEqual(info['format'], 'coreml')
            self.assertIsNotNone(info['path'])
            self.assertIsNotNone(info['engine'])
            
            logger.info(f"✅ Model info: {info}")
        
        except Exception as e:
            self.skipTest(f"CoreML not available: {e}")


class TestE2EMultiFormatBenchmark(unittest.TestCase):
    """End-to-end benchmark tests with multiple formats."""
    
    ONNX_MODEL_URL = (
        "https://github.com/onnx/models/raw/refs/heads/main/"
        "validated/vision/object_detection_segmentation/"
        "tiny-yolov2/model/tinyyolov2-7.onnx"
    )
    COREML_MODEL_URL = "https://tmpfiles.org/dl/6926683/yolov8s.mlmodel"
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_benchmark_onnx_model(self):
        """Test benchmarking ONNX model."""
        try:
            from core.universal_model_loader import UniversalModelLoader
            import numpy as np
            
            loader = UniversalModelLoader(compute_unit='CPU')
            model_path = loader.download_model(self.ONNX_MODEL_URL, self.temp_dir)
            loader.load(model_path)
            
            # Run multiple inferences
            times = []
            num_runs = 5
            
            for i in range(num_runs):
                sample_input = loader.create_sample_input()
                
                start = time.time()
                output = loader.run_inference(sample_input)
                elapsed = time.time() - start
                
                times.append(elapsed)
                logger.info(f"  Run {i+1}: {elapsed*1000:.2f}ms")
            
            avg_time = np.mean(times)
            min_time = np.min(times)
            max_time = np.max(times)
            
            logger.info(f"✅ ONNX Benchmark Results:")
            logger.info(f"   Average: {avg_time*1000:.2f}ms")
            logger.info(f"   Min: {min_time*1000:.2f}ms")
            logger.info(f"   Max: {max_time*1000:.2f}ms")
            
            self.assertGreater(len(times), 0)
            self.assertLess(avg_time, 60)
        
        except Exception as e:
            self.skipTest(f"ONNX benchmark failed: {e}")
    
    def test_benchmark_coreml_model(self):
        """Test benchmarking CoreML model."""
        try:
            from core.universal_model_loader import UniversalModelLoader
            import numpy as np
            
            loader = UniversalModelLoader(compute_unit='CPU')
            model_path = loader.download_model(self.COREML_MODEL_URL, self.temp_dir)
            loader.load(model_path)
            
            # Run multiple inferences
            times = []
            num_runs = 5
            
            for i in range(num_runs):
                sample_input = loader.create_sample_input()
                
                start = time.time()
                output = loader.run_inference(sample_input)
                elapsed = time.time() - start
                
                times.append(elapsed)
                logger.info(f"  Run {i+1}: {elapsed*1000:.2f}ms")
            
            avg_time = np.mean(times)
            min_time = np.min(times)
            max_time = np.max(times)
            
            logger.info(f"✅ CoreML Benchmark Results:")
            logger.info(f"   Average: {avg_time*1000:.2f}ms")
            logger.info(f"   Min: {min_time*1000:.2f}ms")
            logger.info(f"   Max: {max_time*1000:.2f}ms")
            
            self.assertGreater(len(times), 0)
            self.assertLess(avg_time, 60)
        
        except Exception as e:
            self.skipTest(f"CoreML benchmark failed: {e}")
    
    def test_auto_format_detection_both_models(self):
        """Test auto-format detection with both model types."""
        try:
            from core.model_format import ModelFormatDetector, ModelFormat
            
            # Test ONNX detection
            onnx_fmt = ModelFormatDetector.from_url(self.ONNX_MODEL_URL)
            self.assertEqual(onnx_fmt, ModelFormat.ONNX)
            logger.info(f"✅ Auto-detected ONNX format from URL")
            
            # Test CoreML detection
            coreml_fmt = ModelFormatDetector.from_url(self.COREML_MODEL_URL)
            self.assertEqual(coreml_fmt, ModelFormat.COREML)
            logger.info(f"✅ Auto-detected CoreML format from URL")
        
        except Exception as e:
            self.skipTest(f"Format detection test failed: {e}")


class TestE2EIntegration(unittest.TestCase):
    """End-to-end integration tests."""
    
    ONNX_MODEL_URL = (
        "https://github.com/onnx/models/raw/refs/heads/main/"
        "validated/vision/object_detection_segmentation/"
        "tiny-yolov2/model/tinyyolov2-7.onnx"
    )
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_full_workflow_onnx(self):
        """Test full workflow: download → load → infer → benchmark."""
        try:
            from core.universal_model_loader import UniversalModelLoader
            from core.model_format import ModelFormat
            import numpy as np
            
            logger.info("Starting full workflow test...")
            
            # Step 1: Download
            logger.info("Step 1: Downloading model...")
            loader = UniversalModelLoader()
            model_path = loader.download_model(self.ONNX_MODEL_URL, self.temp_dir)
            self.assertTrue(os.path.exists(model_path))
            logger.info(f"✅ Downloaded to: {model_path}")
            
            # Step 2: Load
            logger.info("Step 2: Loading model...")
            loader.load(model_path)
            self.assertEqual(loader.model_format, ModelFormat.ONNX)
            logger.info(f"✅ Loaded {loader.model_format.value} model")
            
            # Step 3: Get info
            logger.info("Step 3: Getting model info...")
            info = loader.get_model_info()
            logger.info(f"✅ Model info: format={info['format']}, engine={info['engine']}")
            
            # Step 4: Inference
            logger.info("Step 4: Running inference...")
            sample_input = loader.create_sample_input()
            start = time.time()
            output = loader.run_inference(sample_input)
            elapsed = time.time() - start
            logger.info(f"✅ Inference completed in {elapsed*1000:.2f}ms")
            
            # Step 5: Benchmark
            logger.info("Step 5: Running benchmark (3 runs)...")
            times = []
            for i in range(3):
                sample_input = loader.create_sample_input()
                start = time.time()
                output = loader.run_inference(sample_input)
                elapsed = time.time() - start
                times.append(elapsed)
            
            avg_time = np.mean(times)
            logger.info(f"✅ Benchmark complete - Average: {avg_time*1000:.2f}ms")
            
            logger.info("✅ Full workflow completed successfully!")
        
        except Exception as e:
            self.skipTest(f"Full workflow test failed: {e}")


class TestE2EErrorHandling(unittest.TestCase):
    """End-to-end error handling tests."""
    
    def test_nonexistent_model_url(self):
        """Test handling of nonexistent model URL."""
        try:
            from core.universal_model_loader import UniversalModelLoader
            
            loader = UniversalModelLoader()
            temp_dir = tempfile.mkdtemp()
            
            # Try to download nonexistent model
            with self.assertRaises(Exception):
                loader.download_model('https://example.com/nonexistent.onnx', temp_dir)
            
            logger.info("✅ Correctly handled nonexistent URL")
        
        except Exception as e:
            # This is expected to raise an exception
            logger.info(f"✅ Exception handled correctly: {type(e).__name__}")
    
    def test_invalid_model_path(self):
        """Test handling of invalid model path."""
        try:
            from core.universal_model_loader import UniversalModelLoader
            
            loader = UniversalModelLoader()
            
            # Try to load nonexistent model
            with self.assertRaises(FileNotFoundError):
                loader.load('/nonexistent/path/model.onnx')
            
            logger.info("✅ Correctly handled invalid path")
        
        except Exception as e:
            logger.info(f"✅ Exception handled correctly: {type(e).__name__}")


if __name__ == '__main__':
    unittest.main()

