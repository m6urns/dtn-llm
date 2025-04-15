from flask import Flask, request, redirect, send_file, jsonify, render_template
import os
import time
from datetime import datetime
import json

from queue import RequestQueue
from web import ConversationManager

app = Flask(__name__)

# Initialize components
request_queue = RequestQueue()
conversation_manager = ConversationManager()

# Placeholder for power monitor (to be implemented in Phase 1)
class MockPowerMonitor:
    def get_current_status(self):
        """Mock power status for testing"""
        return {
            "battery_level": 75.0,
            "solar_output": 15.5,
            "power_consumption": 2.0,
            "temperature": 25.0,
            "timestamp": int(time.time())
        }

power_monitor = MockPowerMonitor()
conversation_manager.power_monitor = power_monitor
conversation_manager.request_queue = request_queue

@app.route('/')
def index():
    """Home page with form to start a new conversation"""
    power_status = power_monitor.get_current_status()
    queue_length = request_queue.get_queue_length()
    
    # List recent conversations
    recent_conversations = []
    if os.path.exists("static/conversations"):
        for conversation_id in os.listdir("static/conversations"):
            try:
                # Get conversation creation time from file modification time
                path = f"static/conversations/{conversation_id}/index.html"
                if os.path.exists(path):
                    mtime = os.path.getmtime(path)
                    time_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
                    recent_conversations.append((conversation_id, time_str))
            except:
                pass
    
    # Sort by most recent first
    recent_conversations.sort(key=lambda x: x[1], reverse=True)
    
    return render_template('index.html', 
                          battery_level=power_status['battery_level'],
                          solar_output=power_status['solar_output'],
                          queue_length=queue_length,
                          recent_conversations=recent_conversations)

@app.route('/new', methods=['POST'])
def new_conversation():
    """Create a new conversation"""
    initial_prompt = request.form.get('prompt')
    
    if not initial_prompt:
        return redirect('/')
    
    # Mock data for testing
    estimated_time = datetime.now()
    
    # Simulate request enqueue
    request_id = request_queue.enqueue(
        None,  # No conversation ID yet
        initial_prompt,
        2.0,  # Mock power estimate 
        estimated_time
    )
    
    # Create conversation and update the queue with its ID
    conversation_id = conversation_manager.create_new_conversation(
        initial_prompt, 
        estimated_time, 
        request_id
    )
    
    # Update the queue entry with the conversation ID
    conn = request_queue.db_path
    import sqlite3
    conn = sqlite3.connect(request_queue.db_path)
    cursor = conn.cursor()
    cursor.execute('UPDATE requests SET conversation_id = ? WHERE id = ?', 
                   (conversation_id, request_id))
    conn.commit()
    conn.close()
    
    # Generate the conversation page
    conversation_manager.update_conversation_page(conversation_id)
    
    return redirect(f'/conversation/{conversation_id}')

@app.route('/conversation/<conversation_id>')
def view_conversation(conversation_id):
    """View a conversation"""
    # Check if conversation exists
    if not conversation_manager.conversation_exists(conversation_id):
        return "Conversation not found", 404
    
    # Simply serve the static HTML file
    return send_file(conversation_manager.get_conversation_path(conversation_id))

@app.route('/submit', methods=['POST'])
def submit_prompt():
    """Submit a new prompt to an existing conversation"""
    conversation_id = request.form.get('conversation_id')
    prompt = request.form.get('prompt')
    
    if not conversation_id or not prompt:
        return redirect('/')
    
    # Add prompt to queue with mock estimated time
    estimated_time = datetime.now()
    request_id = request_queue.enqueue(
        conversation_id,
        prompt,
        2.0,  # Mock power estimate
        estimated_time
    )
    
    # Update conversation page
    conversation_manager.update_conversation_page(conversation_id)
    
    return redirect(f'/conversation/{conversation_id}')

@app.route('/api/status')
def system_status():
    """API endpoint for system status"""
    power_status = power_monitor.get_current_status()
    queue_length = request_queue.get_queue_length()
    
    return jsonify({
        "battery_level": power_status["battery_level"],
        "solar_output": power_status["solar_output"],
        "queue_length": queue_length,
        "timestamp": int(time.time())
    })

@app.route('/download/<conversation_id>')
def download_conversation(conversation_id):
    """Download conversation as text file"""
    requests = request_queue.get_conversation_requests(conversation_id)
    
    text_content = f"Solar LLM Conversation {conversation_id}\n"
    text_content += f"Downloaded on {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    
    for request in requests:
        text_content += f"You: {request['prompt']}\n\n"
        if request['status'] == 'completed' and request['response']:
            text_content += f"AI: {request['response']}\n\n"
    
    response = app.response_class(
        response=text_content,
        mimetype='text/plain',
        headers={'Content-Disposition': f'attachment;filename=conversation-{conversation_id}.txt'}
    )
    return response

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)