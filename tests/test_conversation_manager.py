import os
import pytest
import sys
import uuid
from datetime import datetime, timedelta

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web import ConversationManager
from queue import RequestQueue

@pytest.fixture
def test_dir():
    """Create a temporary test directory for conversations"""
    dir_path = "test_conversations"
    # Create the test directory
    os.makedirs(dir_path, exist_ok=True)
    yield dir_path
    # Clean up after the tests
    import shutil
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)

@pytest.fixture
def test_db():
    """Create a temporary test database"""
    db_path = "test_conversation_queue.db"
    # Remove the test database if it exists
    if os.path.exists(db_path):
        os.remove(db_path)
    yield db_path
    # Clean up after the tests
    if os.path.exists(db_path):
        os.remove(db_path)

class MockPowerMonitor:
    def get_current_status(self):
        """Mock power status for testing"""
        return {
            "battery_level": 75.0,
            "solar_output": 15.5,
            "power_consumption": 2.0,
            "temperature": 25.0,
            "timestamp": int(datetime.now().timestamp())
        }

def test_create_new_conversation(test_dir):
    """Test creating a new conversation without power monitor"""
    manager = ConversationManager(static_pages_dir=test_dir)
    
    prompt = "Test prompt"
    conversation_id = manager.create_new_conversation(prompt)
    
    # Check that the conversation directory was created
    assert os.path.exists(f"{test_dir}/{conversation_id}")
    
    # Check that the HTML file was created
    assert os.path.exists(f"{test_dir}/{conversation_id}/index.html")
    
    # Check that the HTML file contains the prompt
    with open(f"{test_dir}/{conversation_id}/index.html", 'r') as f:
        content = f.read()
        assert prompt in content

def test_create_new_conversation_with_power(test_dir, test_db):
    """Test creating a new conversation with power monitor and request queue"""
    request_queue = RequestQueue(db_path=test_db)
    power_monitor = MockPowerMonitor()
    
    manager = ConversationManager(
        static_pages_dir=test_dir,
        request_queue=request_queue,
        power_monitor=power_monitor
    )
    
    prompt = "Test prompt with power"
    estimated_time = datetime.now() + timedelta(minutes=30)
    
    # Create a request in the queue
    request_id = request_queue.enqueue(
        "temp_conversation_id",
        prompt,
        2.5,
        estimated_time
    )
    
    conversation_id = manager.create_new_conversation(
        prompt, 
        estimated_time, 
        request_id
    )
    
    # Check that the conversation directory was created
    assert os.path.exists(f"{test_dir}/{conversation_id}")
    
    # Check that the HTML file was created
    assert os.path.exists(f"{test_dir}/{conversation_id}/index.html")
    
    # Check that the HTML file contains the prompt and power info
    with open(f"{test_dir}/{conversation_id}/index.html", 'r') as f:
        content = f.read()
        assert prompt in content
        assert "Battery level" in content
        assert "solar output" in content.lower()

def test_update_conversation_page(test_dir, test_db):
    """Test updating a conversation page with completed responses"""
    request_queue = RequestQueue(db_path=test_db)
    power_monitor = MockPowerMonitor()
    
    manager = ConversationManager(
        static_pages_dir=test_dir,
        request_queue=request_queue,
        power_monitor=power_monitor
    )
    
    # Create a conversation
    conversation_id = str(uuid.uuid4())
    os.makedirs(f"{test_dir}/{conversation_id}", exist_ok=True)
    
    # Add some requests to the queue
    prompt1 = "Test prompt 1"
    prompt2 = "Test prompt 2"
    estimated_time = datetime.now() + timedelta(minutes=30)
    
    request_id1 = request_queue.enqueue(
        conversation_id,
        prompt1,
        2.5,
        estimated_time
    )
    
    request_id2 = request_queue.enqueue(
        conversation_id,
        prompt2,
        2.5,
        estimated_time
    )
    
    # Mark the first request as completed with a response
    response = "This is a test response"
    request_queue.update_request_status(request_id1, "completed", response)
    
    # Update the conversation page
    manager.update_conversation_page(conversation_id)
    
    # Check that the HTML file contains both prompts and the response
    with open(f"{test_dir}/{conversation_id}/index.html", 'r') as f:
        content = f.read()
        assert prompt1 in content
        assert prompt2 in content
        assert response in content
        
        # The first request should show as completed
        assert "AI:" in content
        
        # The second request should still be in the queue
        assert "Your request is queued" in content

def test_conversation_exists(test_dir):
    """Test checking if a conversation exists"""
    manager = ConversationManager(static_pages_dir=test_dir)
    
    # Create a conversation
    conversation_id = str(uuid.uuid4())
    os.makedirs(f"{test_dir}/{conversation_id}", exist_ok=True)
    
    # Create an index.html file
    with open(f"{test_dir}/{conversation_id}/index.html", 'w') as f:
        f.write("<html></html>")
    
    # Check that the conversation exists
    assert manager.conversation_exists(conversation_id)
    
    # Check that a non-existent conversation doesn't exist
    assert not manager.conversation_exists("non-existent-id")