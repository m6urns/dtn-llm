import os
import sys
import pytest
import time
import uuid
from datetime import datetime, timedelta

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from queue import RequestQueue
from power_monitor import MockPowerMonitor
from llm_processor import MockLLMProcessor
from scheduler import PowerAwareScheduler


@pytest.fixture
def test_db():
    """Create a temporary test database for the request queue."""
    db_path = "test_scheduler_queue.db"
    # Remove the test database if it exists
    if os.path.exists(db_path):
        os.remove(db_path)
    yield db_path
    # Clean up after the tests
    if os.path.exists(db_path):
        os.remove(db_path)

@pytest.fixture
def power_monitor():
    """Create a mock power monitor for testing."""
    return MockPowerMonitor(
        initial_battery_level=75.0,
        max_solar_output=30.0
    )

@pytest.fixture
def llm_processor(power_monitor):
    """Create a mock LLM processor for testing."""
    return MockLLMProcessor(
        power_monitor=power_monitor,
        processing_speed=50  # Faster for testing
    )

@pytest.fixture
def request_queue(test_db):
    """Create a request queue for testing."""
    return RequestQueue(db_path=test_db)

@pytest.fixture
def scheduler(power_monitor, request_queue, llm_processor):
    """Create a power-aware scheduler for testing."""
    scheduler = PowerAwareScheduler(
        power_monitor=power_monitor,
        request_queue=request_queue,
        llm_processor=llm_processor
    )
    yield scheduler
    # Clean up by stopping the processing thread
    scheduler.stop()
    time.sleep(0.1)  # Give it time to stop


def test_scheduler_initialization(scheduler):
    """Test that the scheduler initializes correctly."""
    assert scheduler.power_monitor is not None
    assert scheduler.request_queue is not None
    assert scheduler.llm_processor is not None
    assert scheduler.processing is False
    assert "base_power" in scheduler.power_calibration_data
    assert "token_processing_power" in scheduler.power_calibration_data
    assert "tokens_per_second" in scheduler.power_calibration_data


def test_estimate_tokens(scheduler):
    """Test the token estimation function."""
    # Empty prompt
    assert scheduler.estimate_tokens("") == 0
    
    # Short prompt
    assert scheduler.estimate_tokens("Hello") == 1
    
    # Longer prompt
    long_prompt = "This is a longer prompt that should have more than a few tokens."
    assert scheduler.estimate_tokens(long_prompt) > 10


def test_estimate_power_requirement(scheduler):
    """Test the power requirement estimation."""
    # Zero tokens
    zero_power = scheduler.estimate_power_requirement(0)
    assert zero_power == scheduler.power_calibration_data["base_power"]
    
    # 100 tokens
    token_power = scheduler.power_calibration_data["token_processing_power"]
    token_count = 100
    expected_power = scheduler.power_calibration_data["base_power"] + (token_count * token_power)
    assert scheduler.estimate_power_requirement(token_count) == expected_power


def test_estimate_processing_time(scheduler):
    """Test the processing time estimation."""
    # Zero tokens
    assert scheduler.estimate_processing_time(0) == 0
    
    # 100 tokens
    token_count = 100
    tokens_per_second = scheduler.power_calibration_data["tokens_per_second"]
    expected_time = token_count / tokens_per_second
    assert scheduler.estimate_processing_time(token_count) == expected_time


def test_enqueue_prompt(scheduler, request_queue):
    """Test enqueueing a prompt."""
    # Create a conversation ID
    conversation_id = str(uuid.uuid4())
    
    # Enqueue a prompt
    prompt = "This is a test prompt."
    request_id, estimated_time = scheduler.enqueue_prompt(conversation_id, prompt)
    
    # Verify the request was added to the queue
    assert request_queue.get_queue_length() == 1
    
    # Verify the request has the correct conversation ID and prompt
    request = request_queue.get_request(request_id)
    assert request is not None
    assert request["conversation_id"] == conversation_id
    assert request["prompt"] == prompt
    assert request["status"] == "queued"
    
    # Verify the estimated time is in the future
    assert isinstance(estimated_time, datetime)
    assert estimated_time > datetime.now()


def test_process_queue(scheduler, request_queue, power_monitor):
    """Test processing a queued request."""
    # Set battery level high enough for processing
    power_monitor.battery_level = 80.0
    
    # Create a conversation ID
    conversation_id = str(uuid.uuid4())
    
    # Enqueue a simple prompt that has a canned response
    prompt = "hello"
    request_id, _ = scheduler.enqueue_prompt(conversation_id, prompt)
    
    # Let the scheduler process for a bit
    time.sleep(2)
    
    # Check that the request was processed
    request = request_queue.get_request(request_id)
    assert request is not None
    assert request["status"] == "completed"
    assert "Hello" in request["response"]  # Should match canned response


def test_low_battery_no_processing(scheduler, request_queue, power_monitor):
    """Test that requests aren't processed when battery is low."""
    # Set battery level too low for processing
    power_monitor.battery_level = 20.0
    
    # Create a conversation ID
    conversation_id = str(uuid.uuid4())
    
    # Enqueue a prompt
    prompt = "This should not be processed due to low battery."
    request_id, _ = scheduler.enqueue_prompt(conversation_id, prompt)
    
    # Let the scheduler try to process for a bit
    time.sleep(2)
    
    # Check that the request is still queued
    request = request_queue.get_request(request_id)
    assert request is not None
    assert request["status"] == "queued"  # Should still be queued, not processed


def test_update_power_calibration(scheduler):
    """Test updating power calibration data."""
    # Create mock power readings
    initial_power = {
        "timestamp": int(time.time()),
        "power": 10.0,
        "voltage": 3.7,
        "current": 2.7,
        "temperature": 25
    }
    
    final_power = {
        "timestamp": int(time.time()) + 10,
        "power": 12.0,
        "voltage": 3.6,
        "current": 3.3,
        "temperature": 26
    }
    
    initial_time = time.time()
    final_time = initial_time + 10
    
    prompt = "Test prompt"
    response = "Test response that is a bit longer to have more tokens"
    
    # Get initial calibration values
    initial_tokens_per_second = scheduler.power_calibration_data["tokens_per_second"]
    initial_token_power = scheduler.power_calibration_data["token_processing_power"]
    
    # Update calibration
    scheduler.update_power_calibration(
        initial_power, 
        final_power, 
        initial_time, 
        final_time, 
        prompt, 
        response
    )
    
    # Values should have changed
    assert scheduler.power_calibration_data["tokens_per_second"] != initial_tokens_per_second
    assert scheduler.power_calibration_data["token_processing_power"] != initial_token_power


def test_callback_function(scheduler, request_queue, power_monitor):
    """Test that the callback function is called when a request completes."""
    # Set battery level high enough for processing
    power_monitor.battery_level = 80.0
    
    # Create a flag to check if callback was called
    callback_called = [False]
    callback_conversation_id = [None]
    
    def test_callback(conversation_id):
        callback_called[0] = True
        callback_conversation_id[0] = conversation_id
    
    # Set the callback function
    scheduler.callback_fn = test_callback
    
    # Create a conversation ID
    conversation_id = str(uuid.uuid4())
    
    # Enqueue a simple prompt that has a canned response
    prompt = "hello"
    scheduler.enqueue_prompt(conversation_id, prompt)
    
    # Let the scheduler process for a bit
    time.sleep(2)
    
    # Check that the callback was called with the correct conversation ID
    assert callback_called[0] is True
    assert callback_conversation_id[0] == conversation_id


def test_get_request_info(scheduler, request_queue):
    """Test getting information about a request."""
    # Create a conversation ID
    conversation_id = str(uuid.uuid4())
    
    # Enqueue a prompt
    prompt = "Test prompt for info"
    request_id, _ = scheduler.enqueue_prompt(conversation_id, prompt)
    
    # Get request info
    request_info = scheduler.get_request_info(request_id)
    
    # Verify the info is correct
    assert request_info is not None
    assert request_info["conversation_id"] == conversation_id
    assert request_info["prompt"] == prompt
    assert request_info["status"] == "queued"
    assert "queue_position" in request_info


def test_get_queue_status(scheduler):
    """Test getting the queue status."""
    # Get queue status
    status = scheduler.get_queue_status()
    
    # Verify the status has the expected fields
    assert "queue_length" in status
    assert "power_status" in status
    assert "processing_active" in status
    
    # Verify power status has the expected fields
    power_status = status["power_status"]
    assert "battery_level" in power_status
    assert "solar_output" in power_status