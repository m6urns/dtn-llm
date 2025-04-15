import os
import pytest
import sqlite3
from datetime import datetime, timedelta
import sys
import uuid

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from queue import RequestQueue

@pytest.fixture
def test_db():
    """Create a temporary test database"""
    db_path = "test_queue.db"
    # Remove the test database if it exists
    if os.path.exists(db_path):
        os.remove(db_path)
    yield db_path
    # Clean up after the tests
    if os.path.exists(db_path):
        os.remove(db_path)

def test_init_db(test_db):
    """Test that the database is initialized correctly"""
    queue = RequestQueue(db_path=test_db)
    
    # Check if the table was created
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='requests'")
    tables = cursor.fetchall()
    conn.close()
    
    assert len(tables) == 1
    assert tables[0][0] == 'requests'

def test_enqueue(test_db):
    """Test enqueueing a request"""
    queue = RequestQueue(db_path=test_db)
    
    conversation_id = str(uuid.uuid4())
    prompt = "Test prompt"
    estimated_power = 2.5
    estimated_completion = datetime.now() + timedelta(minutes=30)
    
    request_id = queue.enqueue(conversation_id, prompt, estimated_power, estimated_completion)
    
    # Verify the request was added
    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM requests WHERE id = ?", (request_id,))
    row = cursor.fetchone()
    conn.close()
    
    assert row is not None
    assert row['conversation_id'] == conversation_id
    assert row['prompt'] == prompt
    assert float(row['estimated_power']) == estimated_power
    assert row['status'] == 'queued'

def test_get_queue_length(test_db):
    """Test getting the queue length"""
    queue = RequestQueue(db_path=test_db)
    
    # Initially the queue should be empty
    assert queue.get_queue_length() == 0
    
    # Add a request
    conversation_id = str(uuid.uuid4())
    prompt = "Test prompt"
    estimated_power = 2.5
    estimated_completion = datetime.now() + timedelta(minutes=30)
    
    queue.enqueue(conversation_id, prompt, estimated_power, estimated_completion)
    
    # Now there should be one request
    assert queue.get_queue_length() == 1
    
    # Add another request
    queue.enqueue(conversation_id, "Another prompt", estimated_power, estimated_completion)
    
    # Now there should be two requests
    assert queue.get_queue_length() == 2

def test_get_request(test_db):
    """Test getting a request by ID"""
    queue = RequestQueue(db_path=test_db)
    
    conversation_id = str(uuid.uuid4())
    prompt = "Test prompt"
    estimated_power = 2.5
    estimated_completion = datetime.now() + timedelta(minutes=30)
    
    request_id = queue.enqueue(conversation_id, prompt, estimated_power, estimated_completion)
    
    # Get the request
    request = queue.get_request(request_id)
    
    assert request is not None
    assert request['conversation_id'] == conversation_id
    assert request['prompt'] == prompt
    assert float(request['estimated_power']) == estimated_power
    assert request['status'] == 'queued'

def test_update_request_status(test_db):
    """Test updating the status of a request"""
    queue = RequestQueue(db_path=test_db)
    
    conversation_id = str(uuid.uuid4())
    prompt = "Test prompt"
    estimated_power = 2.5
    estimated_completion = datetime.now() + timedelta(minutes=30)
    
    request_id = queue.enqueue(conversation_id, prompt, estimated_power, estimated_completion)
    
    # Update the status
    queue.update_request_status(request_id, "processing")
    
    # Verify the status was updated
    request = queue.get_request(request_id)
    assert request['status'] == 'processing'
    
    # Update with a response
    response = "This is a test response"
    queue.update_request_status(request_id, "completed", response)
    
    # Verify both status and response were updated
    request = queue.get_request(request_id)
    assert request['status'] == 'completed'
    assert request['response'] == response

def test_get_next_processable_request(test_db):
    """Test getting the next processable request"""
    queue = RequestQueue(db_path=test_db)
    
    conversation_id = str(uuid.uuid4())
    prompt1 = "Test prompt 1"
    prompt2 = "Test prompt 2"
    estimated_completion = datetime.now() + timedelta(minutes=30)
    
    # Add two requests with different power requirements
    queue.enqueue(conversation_id, prompt1, 5.0, estimated_completion)
    request_id2 = queue.enqueue(conversation_id, prompt2, 2.0, estimated_completion)
    
    # With 3.0 available power, the second request should be processable
    next_request = queue.get_next_processable_request(3.0)
    assert next_request is not None
    assert next_request['prompt'] == prompt2
    assert next_request['id'] == request_id2
    
    # With 1.0 available power, no requests should be processable
    next_request = queue.get_next_processable_request(1.0)
    assert next_request is None

def test_get_conversation_requests(test_db):
    """Test getting all requests for a conversation"""
    queue = RequestQueue(db_path=test_db)
    
    conversation_id = str(uuid.uuid4())
    prompt1 = "Test prompt 1"
    prompt2 = "Test prompt 2"
    estimated_power = 2.5
    estimated_completion = datetime.now() + timedelta(minutes=30)
    
    # Add two requests for the same conversation
    queue.enqueue(conversation_id, prompt1, estimated_power, estimated_completion)
    queue.enqueue(conversation_id, prompt2, estimated_power, estimated_completion)
    
    # Get all requests for the conversation
    requests = queue.get_conversation_requests(conversation_id)
    
    assert len(requests) == 2
    assert requests[0]['prompt'] == prompt1
    assert requests[1]['prompt'] == prompt2