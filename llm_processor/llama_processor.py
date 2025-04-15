import os
import subprocess
import time
import threading
from typing import Optional

from .base_processor import BaseLLMProcessor


class LlamaProcessor(BaseLLMProcessor):
    """
    LLM processor that interfaces with llama.cpp to generate responses
    with power-aware processing.
    """

    def __init__(
        self,
        model_path: str,
        power_monitor=None,
        llama_cpp_path: str = "./llama.cpp/main",
        context_size: int = 2048,
        temperature: float = 0.7
    ):
        """Initialize the Llama processor.

        Args:
            model_path: Path to the llama model file (.gguf)
            power_monitor: Power monitor instance to check power availability
            llama_cpp_path: Path to the llama.cpp executable
            context_size: Context size for model inference
            temperature: Temperature parameter for sampling
        """
        self.model_path = model_path
        self.power_monitor = power_monitor
        self.llama_cpp_path = llama_cpp_path
        self.context_size = context_size
        self.temperature = temperature

        # Check if model file exists
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")

        # Check if llama.cpp executable exists
        if not os.path.exists(llama_cpp_path):
            raise FileNotFoundError(
                f"llama.cpp executable not found: {llama_cpp_path}"
            )

    def generate_response(
        self, prompt: str, max_tokens: Optional[int] = None
    ) -> str:
        """Generate a response using llama.cpp.

        This method runs the llama.cpp executable as a subprocess and monitors
        power during generation.

        Args:
            prompt: The input prompt text
            max_tokens: Optional maximum number of tokens to generate

        Returns:
            str: The generated response
        """
        # Configure max tokens based on available power if not specified
        if max_tokens is None:
            max_tokens = self.determine_max_tokens()

        # Set process to None initially
        process = None

        try:
            # Start power monitoring if available
            if self.power_monitor:
                self.power_monitor.set_processing_state(True)

            # Start time for measuring duration
            start_time = time.time()

            # Build command for llama.cpp
            cmd = [
                self.llama_cpp_path,
                "-m", self.model_path,
                "-p", prompt,
                "--ctx_size", str(self.context_size),
                "--temp", str(self.temperature),
                "--n_predict", str(max_tokens),
                # Disable memory mapping for predictable power usage
                "--no-mmap"
            ]

            # Start llama.cpp process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
            )

            # Create thread to monitor power
            stop_flag = threading.Event()
            if self.power_monitor:
                power_thread = threading.Thread(
                    target=self._monitor_power_during_generation,
                    args=(process, stop_flag)
                )
                power_thread.daemon = True
                power_thread.start()

            # Collect output
            output = ""
            for line in process.stdout:
                output += line

            # Stop power monitoring thread
            if self.power_monitor:
                stop_flag.set()
                power_thread.join(timeout=2)

            # Wait for process to complete
            process.wait()

            # End time for measuring duration
            end_time = time.time()

            # Calculate power used
            if self.power_monitor:
                duration = end_time - start_time
                # Simulate battery discharge (5W power draw during processing)
                self.power_monitor.simulate_battery_change(duration, 5.0)

            # Clean up the output - remove prompt and llama.cpp formatting
            response = self._clean_response(output, prompt)

            return response

        except Exception as e:
            # Clean up in case of error
            if process and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except Exception:
                    process.kill()

            return f"Error generating response: {e}"

        finally:
            # Always reset processing state
            if self.power_monitor:
                self.power_monitor.set_processing_state(False)

    def _monitor_power_during_generation(self, process, stop_flag):
        """Monitor power levels during generation and stop if battery is low.

        Args:
            process: The subprocess running llama.cpp
            stop_flag: Threading event to signal when to stop monitoring
        """
        while process.poll() is None and not stop_flag.is_set():
            # Check power status
            if self.power_monitor:
                battery_level = self.power_monitor.estimate_battery_level()

                # If battery gets too low, terminate the process
                if battery_level < 20:
                    # Send terminate signal to process
                    try:
                        process.terminate()
                        # Give it 5 seconds to terminate gracefully
                        process.wait(timeout=5)
                    except Exception:
                        # Force kill if it doesn't terminate
                        process.kill()

                    break

            # Sleep briefly to avoid constant checking
            time.sleep(5)

    def _clean_response(self, output: str, prompt: str) -> str:
        """Clean llama.cpp output by removing prompt and system text.

        Args:
            output: Raw output from llama.cpp
            prompt: Original prompt that was sent

        Returns:
            str: Cleaned response text
        """
        # Basic cleaning - handle different llama.cpp output formats
        # Typically llama.cpp includes the prompt in the output

        # Try to find the prompt in the output
        if prompt in output:
            response = output.split(prompt, 1)[1].strip()
        else:
            # If prompt not found, just return the output
            response = output.strip()

        # Additional cleanup for specific llama.cpp output patterns
        # Remove any trailing special tokens or formatting
        response = response.replace("<end>", "").replace("<eos>", "").strip()

        # If response gets truncated due to power issues, add a note
        if (self.power_monitor and 
                self.power_monitor.estimate_battery_level() < 25):
            response += (
                "\n[Note: Response may have been truncated due to low power]"
            )

        return response

    def determine_max_tokens(self) -> int:
        """Determine maximum response length based on power availability.

        Returns:
            int: Maximum number of tokens to generate
        """
        if not self.power_monitor:
            return 1024  # Default if no power monitor

        battery_level = self.power_monitor.estimate_battery_level()

        if battery_level > 80:
            return 2048  # Full responses when battery is high
        elif battery_level > 50:
            return 1024  # Medium responses
        elif battery_level > 30:
            return 512   # Short responses when power is low
        else:
            return 256   # Very short responses when power is critical

    def estimate_token_count(self, text: str) -> int:
        """Estimate number of tokens in text.

        This is a simple approximation. Actual tokenization depends on the
        specific model's tokenizer.

        Args:
            text: Input text

        Returns:
            int: Estimated token count
        """
        # Very simple approximation - 100 tokens is roughly 75 words
        # or about 4 characters per token on average
        if not text:
            return 0
        return max(1, len(text) // 4)