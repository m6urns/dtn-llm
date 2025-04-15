import time
import random
from typing import Dict, Any, Optional, List

from .base_processor import BaseLLMProcessor


class MockLLMProcessor(BaseLLMProcessor):
    """Mock LLM processor for testing without real LLM."""
    
    def __init__(self, power_monitor=None, processing_speed: int = 10):
        """Initialize the mock LLM processor.
        
        Args:
            power_monitor: Power monitor instance to check power availability
            processing_speed: Tokens processed per second for simulation
        """
        self.power_monitor = power_monitor
        self.processing_speed = processing_speed
        
        # Pre-defined responses for testing
        self.canned_responses = {
            "hello": "Hello! How can I assist you today?",
            "time": "I'm sorry, I don't have access to the current time.",
            "weather": "I don't have access to weather information.",
            "help": "I'm a simulated LLM processor for testing the solar-powered LLM system."
        }
    
    def generate_response(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """Generate a mock response to the prompt.
        
        This method simulates LLM processing time based on prompt length.
        
        Args:
            prompt: The input prompt text
            max_tokens: Optional maximum number of tokens to generate
            
        Returns:
            str: The generated response
        """
        # Estimate tokens in the prompt (simple approximation)
        prompt_tokens = len(prompt.split())
        
        # Set max response tokens
        if max_tokens is None:
            max_tokens = self.determine_max_tokens()
        
        # Check for canned responses
        for key, response in self.canned_responses.items():
            if key in prompt.lower():
                canned_response = response
                # Truncate if necessary
                if len(canned_response.split()) > max_tokens:
                    words = canned_response.split()[:max_tokens]
                    canned_response = " ".join(words) + "..."
                
                # Simulate processing time
                estimated_tokens = len(canned_response.split())
                processing_time = estimated_tokens / self.processing_speed
                
                # Simulate power consumption during processing if power monitor is available
                start_time = time.time()
                if self.power_monitor:
                    self.power_monitor.set_processing_state(True)
                
                # Simulate processing
                time.sleep(processing_time)
                
                # End processing simulation
                if self.power_monitor:
                    elapsed_time = time.time() - start_time
                    # Assume 5W during processing
                    self.power_monitor.simulate_battery_change(elapsed_time, 5.0)
                    self.power_monitor.set_processing_state(False)
                
                return canned_response
        
        # If no canned response, generate a generic one
        response_length = min(max_tokens, random.randint(20, 50))
        
        # Generate nonsense words for testing
        words = []
        for _ in range(response_length):
            word_length = random.randint(3, 10)
            word = ''.join(random.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(word_length))
            words.append(word)
        
        response = " ".join(words)
        
        # Simulate processing time
        processing_time = response_length / self.processing_speed
        
        # Simulate power consumption during processing if power monitor is available
        start_time = time.time()
        if self.power_monitor:
            self.power_monitor.set_processing_state(True)
        
        # Simulate processing
        time.sleep(processing_time)
        
        # End processing simulation
        if self.power_monitor:
            elapsed_time = time.time() - start_time
            # Assume 5W during processing
            self.power_monitor.simulate_battery_change(elapsed_time, 5.0)
            self.power_monitor.set_processing_state(False)
        
        return f"Mock response to: {prompt[:30]}... \n\n{response}"
    
    def determine_max_tokens(self) -> int:
        """Determine maximum response length based on power availability."""
        if not self.power_monitor:
            return 1024  # Default if no power monitor
        
        battery_level = self.power_monitor.estimate_battery_level()
        
        if battery_level > 80:
            return 2048  # Full responses when battery is high
        elif battery_level > 50:
            return 1024  # Medium responses
        else:
            return 512   # Short responses when power is low