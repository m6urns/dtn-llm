from flask import Flask, request, redirect, send_file, jsonify, render_template
import os
import time
from datetime import datetime
import json
import argparse

from queue import RequestQueue
from web import ConversationManager
from power_monitor import MockPowerMonitor
from llm_processor import MockLLMProcessor, LlamaProcessor
from scheduler import PowerAwareScheduler

app = Flask(__name__)

# Setup command line arguments
parser = argparse.ArgumentParser(description='Solar-powered LLM system with delay-tolerant networking')
parser.add_argument('--model', help='Path to GGUF model file for llama.cpp')
parser.add_argument('--llama-cpp', default='./llama.cpp/main', help='Path to llama.cpp executable')
parser.add_argument('--use-mock', action='store_true', help='Use mock LLM processor instead of real one')
args = parser.parse_args()

# Initialize components
power_monitor = MockPowerMonitor(initial_battery_level=75.0, max_solar_output=30.0)
request_queue = RequestQueue()

# Initialize LLM processor (mock or real)
if args.use_mock or not args.model:
    print("Using mock LLM processor")
    llm_processor = MockLLMProcessor(power_monitor=power_monitor)
else:
    # Check if model file and llama.cpp executable exist
    if not os.path.exists(args.model):
        print(f"Error: Model file not found: {args.model}")
        print("Falling back to mock LLM processor")
        llm_processor = MockLLMProcessor(power_monitor=power_monitor)
    elif not os.path.exists(args.llama_cpp):
        print(f"Error: llama.cpp executable not found: {args.llama_cpp}")
        print("Falling back to mock LLM processor")
        llm_processor = MockLLMProcessor(power_monitor=power_monitor)
    else:
        print(f"Using llama.cpp with model: {args.model}")
        llm_processor = LlamaProcessor(
            model_path=args.model,
            power_monitor=power_monitor,
            llama_cpp_path=args.llama_cpp
        )

# Initialize scheduler with a callback to update conversation pages
def update_conversation_callback(conversation_id):
    """Callback function to update conversation page when a request completes."""
    if conversation_manager:
        conversation_manager.update_conversation_page(conversation_id)

scheduler = PowerAwareScheduler(
    power_monitor=power_monitor, 
    request_queue=request_queue, 
    llm_processor=llm_processor,
    callback_fn=update_conversation_callback
)

# Initialize conversation manager after scheduler to avoid circular references
conversation_manager = ConversationManager(
    static_pages_dir="static/conversations",
    request_queue=request_queue,
    power_monitor=power_monitor
)

@app.route('/')
def index():
    """Home page with form to start a new conversation."""
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
    """Create a new conversation."""
    initial_prompt = request.form.get('prompt')
    
    if not initial_prompt:
        return redirect('/')
    
    # Add prompt to scheduler queue
    request_id, estimated_time = scheduler.enqueue_prompt(None, initial_prompt)
    
    # Create conversation and update the queue with its ID
    conversation_id = conversation_manager.create_new_conversation(
        initial_prompt, 
        estimated_time, 
        request_id
    )
    
    # Update the queue entry with the conversation ID
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
    """View a conversation."""
    # Check if conversation exists
    if not conversation_manager.conversation_exists(conversation_id):
        return "Conversation not found", 404
    
    # Simply serve the static HTML file
    return send_file(conversation_manager.get_conversation_path(conversation_id))

@app.route('/submit', methods=['POST'])
def submit_prompt():
    """Submit a new prompt to an existing conversation."""
    conversation_id = request.form.get('conversation_id')
    prompt = request.form.get('prompt')
    
    if not conversation_id or not prompt:
        return redirect('/')
    
    # Add prompt to scheduler queue
    request_id, estimated_time = scheduler.enqueue_prompt(conversation_id, prompt)
    
    # Update conversation page
    conversation_manager.update_conversation_page(conversation_id)
    
    return redirect(f'/conversation/{conversation_id}')

@app.route('/api/status')
def system_status():
    """API endpoint for system status."""
    power_status = power_monitor.get_current_status()
    queue_status = scheduler.get_queue_status()
    
    return jsonify({
        "battery_level": power_status["battery_level"],
        "solar_output": power_status["solar_output"],
        "queue_length": queue_status["queue_length"],
        "processing_active": queue_status["processing_active"],
        "timestamp": int(time.time())
    })

@app.route('/api/request/<request_id>')
def request_status(request_id):
    """API endpoint for specific request status."""
    return jsonify(scheduler.get_request_info(request_id))

@app.route('/download/<conversation_id>')
def download_conversation(conversation_id):
    """Download conversation as text file."""
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

# For testing purposes
@app.route('/simulate/charge')
def simulate_charge():
    """Simulate battery charging."""
    amount = float(request.args.get('amount', 10))
    current = power_monitor.battery_level
    power_monitor.battery_level = min(100, current + amount)
    return jsonify({"status": "ok", "battery_level": power_monitor.battery_level})

@app.route('/simulate/discharge')
def simulate_discharge():
    """Simulate battery discharging."""
    amount = float(request.args.get('amount', 10))
    current = power_monitor.battery_level
    power_monitor.battery_level = max(0, current - amount)
    return jsonify({"status": "ok", "battery_level": power_monitor.battery_level})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)