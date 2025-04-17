import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, Optional, List, Callable

from queue import RequestQueue
from power_monitor import BasePowerMonitor
from llm_processor import BaseLLMProcessor


class PowerAwareScheduler:
    """
    Scheduler that decides when to process requests based on power availability
    and provides time estimates to users.
    """
    
    def __init__(self, 
                 power_monitor: BasePowerMonitor, 
                 request_queue: RequestQueue, 
                 llm_processor: BaseLLMProcessor,
                 callback_fn: Optional[Callable[[str], None]] = None,
                 immediate_mode: bool = False):
        """Initialize the power-aware scheduler.
        
        Args:
            power_monitor: Power monitor instance
            request_queue: Request queue instance
            llm_processor: LLM processor instance
            callback_fn: Optional callback function when a request completes
            immediate_mode: Process prompts immediately without waiting for scheduled time
        """
        self.power_monitor = power_monitor
        self.request_queue = request_queue
        self.llm_processor = llm_processor
        self.callback_fn = callback_fn
        self.processing = False
        self.stop_processing = False
        self.immediate_mode = immediate_mode
        self.power_calibration_data = self.load_power_calibration_data()
        
    def load_power_calibration_data(self) -> Dict[str, float]:
        """Load power calibration data from file or create default."""
        try:
            if os.path.exists("power_calibration_data.json"):
                with open("power_calibration_data.json", "r") as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading calibration data: {e}")
            
        # Default power estimates if no calibration data exists
        return {
            "base_power": 2.0,  # Watts
            "token_processing_power": 0.05,  # Watts per token
            "tokens_per_second": 10  # Tokens processed per second
        }
    
    def save_power_calibration_data(self) -> None:
        """Save power calibration data to file."""
        try:
            with open("power_calibration_data.json", "w") as f:
                json.dump(self.power_calibration_data, f)
        except Exception as e:
            print(f"Error saving calibration data: {e}")
    
    def estimate_tokens(self, prompt: str) -> int:
        """Estimate number of tokens in prompt.
        
        This is a simple approximation. In a real implementation, you would use
        a tokenizer matching your LLM.
        
        Args:
            prompt: The prompt text
            
        Returns:
            int: Estimated number of tokens
        """
        # Simple estimation: 4 characters per token on average
        if not prompt:
            return 0
        return max(1, len(prompt) // 4)
    
    def estimate_power_requirement(self, token_count: int) -> float:
        """Estimate power requirement for processing a request.
        
        Args:
            token_count: Number of tokens to process
            
        Returns:
            float: Estimated power requirement in Watts
        """
        # Base power + additional power per token
        return self.power_calibration_data["base_power"] + \
               (token_count * self.power_calibration_data["token_processing_power"])
    
    def estimate_processing_time(self, token_count: int) -> float:
        """Estimate time needed to process tokens.
        
        Args:
            token_count: Number of tokens to process
            
        Returns:
            float: Estimated processing time in seconds
        """
        tokens_per_second = self.power_calibration_data["tokens_per_second"]
        return token_count / tokens_per_second if tokens_per_second > 0 else 60.0
    
    def enqueue_prompt(self, conversation_id: str, prompt: str) -> Tuple[str, datetime]:
        """Add prompt to queue with power estimation.
        
        Args:
            conversation_id: ID of the conversation
            prompt: The prompt text
            
        Returns:
            Tuple of request_id and estimated completion datetime
        """
        # Estimate tokens and power requirements
        token_count = self.estimate_tokens(prompt)
        power_needed = self.estimate_power_requirement(token_count)
        processing_time = self.estimate_processing_time(token_count)
        
        # Calculate estimated completion time
        now = datetime.now()
        queue_delay = timedelta(seconds=60 * self.request_queue.get_queue_length())
        
        # In immediate mode, just use a short delay (current time + processing time)
        if self.immediate_mode:
            process_delay = timedelta(seconds=processing_time)
            estimated_completion = now + process_delay + queue_delay
        else:
            # Get power prediction for coming hours
            power_prediction = self.power_monitor.predict_future_availability(24)
            
            # Default to a far future time
            estimated_completion = now + timedelta(hours=24)
            
            # Find earliest time when power will be sufficient
            for i, prediction in enumerate(power_prediction):
                if prediction["processing_capable"] and power_needed <= prediction["solar_output"]:
                    hour_delay = timedelta(hours=i)
                    process_delay = timedelta(seconds=processing_time)
                    candidate_time = now + hour_delay + process_delay + queue_delay
                    
                    # Take the earliest time
                    if candidate_time < estimated_completion:
                        estimated_completion = candidate_time
                    
                    # If we found a time within the next few hours, we can stop looking
                    if i < 6:  # Within 6 hours
                        break
        
        # Add to queue
        request_id = self.request_queue.enqueue(
            conversation_id, 
            prompt, 
            power_needed, 
            estimated_completion
        )
        
        # Start processing loop if not already running
        if not self.processing:
            self.start_processing()
            
        return request_id, estimated_completion
    
    def start_processing(self) -> None:
        """Start the queue processing loop in a separate thread."""
        if not self.processing:
            self.processing = True
            self.stop_processing = False
            threading.Thread(target=self.process_queue_loop).start()
    
    def stop(self) -> None:
        """Stop the queue processing loop."""
        self.stop_processing = True
    
    def process_queue_loop(self) -> None:
        """Main loop for processing queued requests."""
        self.processing = True
        print(f"[DEBUG] Scheduler: Starting queue processing loop in {'immediate' if self.immediate_mode else 'normal'} mode")
        
        while not self.stop_processing:
            # Check current power availability
            power_status = self.power_monitor.get_current_status()
            available_power = power_status["solar_output"]
            print(f"[DEBUG] Scheduler: Power status - battery: {power_status['battery_level']:.2f}%, solar: {available_power:.2f}W")
            
            # In immediate mode, we process if battery > 30%, regardless of solar output
            # In normal mode, we need both battery > 30% and sufficient solar power
            if power_status["battery_level"] > 30:
                # Get next request that can be processed with available power
                print(f"[DEBUG] Scheduler: Looking for next processable request (immediate_mode={self.immediate_mode})")
                next_request = self.request_queue.get_next_processable_request(available_power, self.immediate_mode)
                
                if next_request:
                    # Update status to processing
                    print(f"[DEBUG] Scheduler: Processing request id={next_request['id']}, conversation_id={next_request['conversation_id']}")
                    print(f"[DEBUG] Scheduler: Prompt: {next_request['prompt'][:50]}...")
                    self.request_queue.update_request_status(next_request["id"], "processing")
                    
                    # Process the request
                    try:
                        # Monitor power during processing
                        initial_power = self.power_monitor.get_current_power_reading()
                        initial_time = time.time()
                        
                        print("[DEBUG] Scheduler: Calling LLM processor to generate response")
                        # Generate response
                        response = self.llm_processor.generate_response(next_request["prompt"])
                        
                        # Record final power usage
                        final_power = self.power_monitor.get_current_power_reading()
                        final_time = time.time()
                        
                        print(f"[DEBUG] Scheduler: Response generation completed in {final_time - initial_time:.2f} seconds")
                        
                        # Update power calibration data
                        self.update_power_calibration(
                            initial_power, 
                            final_power, 
                            initial_time,
                            final_time,
                            next_request["prompt"], 
                            response
                        )
                        
                        # Update request status to completed
                        print(f"[DEBUG] Scheduler: Updating request status to completed")
                        self.request_queue.update_request_status(
                            next_request["id"], 
                            "completed", 
                            response
                        )
                        
                        # Call callback function if provided
                        if self.callback_fn:
                            try:
                                # Check if we have a valid conversation_id
                                conversation_id = next_request.get("conversation_id")
                                if conversation_id and conversation_id != "None":
                                    print(f"[DEBUG] Scheduler: Calling callback for conversation_id={conversation_id}")
                                    self.callback_fn(conversation_id)
                                else:
                                    print(f"[DEBUG] Scheduler: No valid conversation_id found, response won't be displayed")
                                    # Try updating the UI for recent requests
                                    conn = sqlite3.connect(self.request_queue.db_path)
                                    conn.row_factory = sqlite3.Row
                                    cursor = conn.cursor()
                                    cursor.execute('SELECT conversation_id FROM requests WHERE id = ?', (next_request["id"],))
                                    row = cursor.fetchone()
                                    if row and row['conversation_id'] and row['conversation_id'] != "None":
                                        print(f"[DEBUG] Scheduler: Found updated conversation_id={row['conversation_id']}, updating page")
                                        self.callback_fn(row['conversation_id'])
                                    conn.close()
                            except Exception as e:
                                print(f"[DEBUG] Error in callback: {e}")
                        
                    except Exception as e:
                        print(f"[DEBUG] Error processing request: {e}")
                        import traceback
                        print(f"[DEBUG] Traceback: {traceback.format_exc()}")
                        self.request_queue.update_request_status(next_request["id"], "failed")
                else:
                    # No processable requests, sleep
                    print("[DEBUG] Scheduler: No processable requests found, sleeping")
                    time.sleep(10)
            else:
                # Battery too low, sleep
                print(f"[DEBUG] Scheduler: Battery level too low ({power_status['battery_level']:.2f}%), sleeping")
                time.sleep(30)
            
            # Check if queue is empty and no active processing
            queue_length = self.request_queue.get_queue_length()
            print(f"[DEBUG] Scheduler: Current queue length: {queue_length}")
            if queue_length == 0:
                print("[DEBUG] Scheduler: Queue empty, stopping processing loop")
                break
                
        self.processing = False
        print("[DEBUG] Scheduler: Processing loop stopped")
    
    def update_power_calibration(self, 
                                initial_power: Dict[str, Any], 
                                final_power: Dict[str, Any],
                                initial_time: float,
                                final_time: float,
                                prompt: str, 
                                response: str) -> None:
        """Update power calibration data based on actual usage.
        
        Args:
            initial_power: Power readings before processing
            final_power: Power readings after processing
            initial_time: Timestamp before processing
            final_time: Timestamp after processing
            prompt: The prompt text
            response: The generated response
        """
        # Calculate time elapsed
        time_elapsed = final_time - initial_time
        if time_elapsed <= 0:
            return
            
        # Calculate average power used
        if "power" in initial_power and "power" in final_power:
            average_power = (final_power["power"] + initial_power["power"]) / 2
        else:
            # Default if power readings aren't available
            average_power = self.power_calibration_data["base_power"]
        
        energy_used = average_power * (time_elapsed / 3600)  # Watt-hours
        
        # Calculate tokens
        prompt_tokens = self.estimate_tokens(prompt)
        response_tokens = self.estimate_tokens(response)
        total_tokens = prompt_tokens + response_tokens
        
        # Update calibration data
        if total_tokens > 0:
            tokens_per_second = total_tokens / time_elapsed
            token_processing_power = (average_power - self.power_calibration_data["base_power"]) / total_tokens
            
            # Update with weighted average (90% old, 10% new)
            self.power_calibration_data["tokens_per_second"] = (
                self.power_calibration_data["tokens_per_second"] * 0.9 + tokens_per_second * 0.1
            )
            self.power_calibration_data["token_processing_power"] = (
                self.power_calibration_data["token_processing_power"] * 0.9 + token_processing_power * 0.1
            )
            
            # Save updated calibration data
            self.save_power_calibration_data()
    
    def get_request_info(self, request_id: str) -> Dict[str, Any]:
        """Get information about a specific request.
        
        Args:
            request_id: The ID of the request
            
        Returns:
            Dict with request information, including status and estimated time
        """
        request = self.request_queue.get_request(request_id)
        if not request:
            return {"error": "Request not found"}
        
        # Add queue position if request is queued
        if request["status"] == "queued":
            position = self.request_queue.get_queue_position(request_id)
            request["queue_position"] = position
        
        return request
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get overall queue status.
        
        Returns:
            Dict with queue length and power status
        """
        return {
            "queue_length": self.request_queue.get_queue_length(),
            "power_status": self.power_monitor.get_current_status(),
            "processing_active": self.processing
        }