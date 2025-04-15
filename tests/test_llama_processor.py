import os
import pytest
import unittest
from unittest.mock import patch, MagicMock, mock_open
import subprocess
from llm_processor import LlamaProcessor
from power_monitor import MockPowerMonitor


class TestLlamaProcessor(unittest.TestCase):
    """Tests for LlamaProcessor class."""
    
    def setUp(self):
        # Create mocks for dependencies
        self.mock_power_monitor = MockPowerMonitor(
            initial_battery_level=75.0,
            max_solar_output=30.0
        )
        
        # Create patch for os.path.exists to make it return True
        self.path_exists_patch = patch('os.path.exists', return_value=True)
        self.path_exists_mock = self.path_exists_patch.start()
        
        # Create patch for subprocess.Popen
        self.popen_patch = patch('subprocess.Popen')
        self.popen_mock = self.popen_patch.start()
        
        # Setup mock process
        self.mock_process = MagicMock()
        self.mock_process.stdout = ["Mock response line 1\n", "Mock response line 2\n"]
        self.mock_process.poll.return_value = None  # Process is running
        self.mock_process.wait.return_value = 0     # Exit code 0
        self.popen_mock.return_value = self.mock_process
        
    def tearDown(self):
        # Stop all patches
        self.path_exists_patch.stop()
        self.popen_patch.stop()
    
    def test_init(self):
        """Test initialization of LlamaProcessor."""
        processor = LlamaProcessor(
            model_path="/path/to/model.gguf",
            power_monitor=self.mock_power_monitor,
            llama_cpp_path="/path/to/llama.cpp"
        )
        
        # Verify attributes
        self.assertEqual(processor.model_path, "/path/to/model.gguf")
        self.assertEqual(processor.llama_cpp_path, "/path/to/llama.cpp")
        self.assertEqual(processor.context_size, 2048)
        self.assertEqual(processor.temperature, 0.7)
        self.assertEqual(processor.power_monitor, self.mock_power_monitor)

    def test_init_file_not_found(self):
        """Test initialization with missing files."""
        # Set os.path.exists to return False
        self.path_exists_mock.return_value = False
        
        # Verify FileNotFoundError is raised
        with self.assertRaises(FileNotFoundError):
            LlamaProcessor(
                model_path="/path/to/model.gguf",
                power_monitor=self.mock_power_monitor
            )
    
    def test_generate_response(self):
        """Test generating response from llama.cpp."""
        processor = LlamaProcessor(
            model_path="/path/to/model.gguf",
            power_monitor=self.mock_power_monitor,
            llama_cpp_path="/path/to/llama.cpp"
        )
        
        # Test with mock subprocess
        response = processor.generate_response("Test prompt")
        
        # Verify subprocess was called with correct arguments
        self.popen_mock.assert_called_once()
        args, kwargs = self.popen_mock.call_args
        self.assertEqual(kwargs['text'], True)
        self.assertEqual(args[0][0], "/path/to/llama.cpp")
        self.assertEqual(args[0][1], "-m")
        self.assertEqual(args[0][2], "/path/to/model.gguf")
        self.assertEqual(args[0][3], "-p")
        self.assertEqual(args[0][4], "Test prompt")
        
        # Verify power monitor was used
        self.assertEqual(self.mock_power_monitor.is_processing, False)
    
    def test_determine_max_tokens(self):
        """Test max token determination based on battery level."""
        processor = LlamaProcessor(
            model_path="/path/to/model.gguf",
            power_monitor=self.mock_power_monitor,
            llama_cpp_path="/path/to/llama.cpp"
        )
        
        # Set different battery levels and verify token limits
        self.mock_power_monitor.battery_level = 90
        self.assertEqual(processor.determine_max_tokens(), 2048)
        
        self.mock_power_monitor.battery_level = 60
        self.assertEqual(processor.determine_max_tokens(), 1024)
        
        self.mock_power_monitor.battery_level = 40
        self.assertEqual(processor.determine_max_tokens(), 512)
        
        self.mock_power_monitor.battery_level = 25
        self.assertEqual(processor.determine_max_tokens(), 256)
    
    def test_clean_response(self):
        """Test cleaning llama.cpp output."""
        processor = LlamaProcessor(
            model_path="/path/to/model.gguf",
            power_monitor=self.mock_power_monitor,
            llama_cpp_path="/path/to/llama.cpp"
        )
        
        # Test with prompt in output
        output = "Test prompt\nThis is the response"
        clean = processor._clean_response(output, "Test prompt")
        self.assertEqual(clean, "This is the response")
        
        # Test with special tokens
        output = "Test prompt\nThis is the response<end>"
        clean = processor._clean_response(output, "Test prompt")
        self.assertEqual(clean, "This is the response")
        
        # Test with low battery
        self.mock_power_monitor.battery_level = 20
        output = "Test prompt\nThis is the response"
        clean = processor._clean_response(output, "Test prompt")
        self.assertTrue("Response may have been truncated" in clean)
    
    def test_estimate_token_count(self):
        """Test token count estimation."""
        processor = LlamaProcessor(
            model_path="/path/to/model.gguf",
            power_monitor=self.mock_power_monitor,
            llama_cpp_path="/path/to/llama.cpp"
        )
        
        # Test with various text lengths
        self.assertEqual(processor.estimate_token_count(""), 0)
        self.assertEqual(processor.estimate_token_count("test"), 1)
        self.assertEqual(processor.estimate_token_count("a" * 100), 25)
        

if __name__ == '__main__':
    pytest.main()