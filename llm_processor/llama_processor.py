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

        # Check if llama.cpp executable exists and is executable
        if not os.path.exists(llama_cpp_path):
            raise FileNotFoundError(
                f"llama.cpp executable not found: {llama_cpp_path}. "
                f"Make sure to provide the path to the compiled binary (usually named 'main')."
            )
        
        # Check if it's actually executable
        if not os.access(llama_cpp_path, os.X_OK):
            raise PermissionError(
                f"File exists but is not executable: {llama_cpp_path}. "
                f"Make sure you're pointing to the compiled binary, not a source file."
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
            print(f"[DEBUG] LlamaProcessor: Starting to process prompt: {prompt[:30]}...")
            print(f"[DEBUG] LlamaProcessor: Model path: {self.model_path}")
            print(f"[DEBUG] LlamaProcessor: Llama.cpp path: {self.llama_cpp_path}")
            
            # Start power monitoring if available
            if self.power_monitor:
                self.power_monitor.set_processing_state(True)
                print(f"[DEBUG] Power status: {self.power_monitor.get_current_status()}")

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
            
            print(f"[DEBUG] Executing command: {' '.join(cmd)}")

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
            print("[DEBUG] Reading output from llama.cpp...")
            for line in process.stdout:
                output += line
                print(f"[DEBUG] llama.cpp output: {line.strip()}")

            # Read from stderr in a non-blocking way
            from fcntl import fcntl, F_GETFL, F_SETFL
            import os
            
            # Set stderr to non-blocking mode
            flags = fcntl(process.stderr, F_GETFL)
            fcntl(process.stderr, F_SETFL, flags | os.O_NONBLOCK)
            
            # Try to read any stderr output
            try:
                stderr_output = process.stderr.read()
                if stderr_output:
                    print(f"[DEBUG] llama.cpp stderr: {stderr_output}")
            except Exception as e:
                print(f"[DEBUG] Error reading stderr: {e}")

            # Stop power monitoring thread
            if self.power_monitor:
                stop_flag.set()
                power_thread.join(timeout=2)

            # Wait for process to complete
            returncode = process.wait()
            print(f"[DEBUG] llama.cpp process completed with return code: {returncode}")

            # End time for measuring duration
            end_time = time.time()
            processing_duration = end_time - start_time
            print(f"[DEBUG] Processing took {processing_duration:.2f} seconds")

            # Calculate power used
            if self.power_monitor:
                # Simulate battery discharge (5W power draw during processing)
                self.power_monitor.simulate_battery_change(processing_duration, 5.0)
                print(f"[DEBUG] Updated battery level: {self.power_monitor.estimate_battery_level():.2f}%")

            # Clean up the output - remove prompt and llama.cpp formatting
            response = self._clean_response(output, prompt)
            print(f"[DEBUG] Generated response: {response[:100]}...")

            return response

        except Exception as e:
            # Clean up in case of error
            print(f"[DEBUG] Error in LlamaProcessor: {str(e)}")
            import traceback
            print(f"[DEBUG] Traceback: {traceback.format_exc()}")
            
            if process and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                    print("[DEBUG] Process terminated")
                except Exception as term_e:
                    print(f"[DEBUG] Error terminating process: {term_e}")
                    process.kill()
                    print("[DEBUG] Process killed")

            error_message = f"Error generating response with llama.cpp: {e}"
            
            # Add helpful information to the error message
            if "[Errno 8] Exec format error" in str(e):
                error_message += "\n\nThis error usually means the file exists but is not an executable binary."
                error_message += "\nMake sure you're using the 'main' executable from llama.cpp, not the source code file."
                error_message += "\nTry running with: --llama-cpp /home/matt/projects/llama.cpp/main"
            elif "No such file or directory" in str(e):
                error_message += "\n\nThe executable file was not found. Check the path."
            elif "Permission denied" in str(e):
                error_message += "\n\nThe file exists but cannot be executed. Try: chmod +x [path-to-executable]"
                
            return error_message

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