from flask import Flask, request, redirect, send_file, jsonify, render_template
import os
import time
import subprocess
from datetime import datetime
import json
import argparse
import logging

from queue import RequestQueue
from web import ConversationManager
from power_monitor import MockPowerMonitor, TC66PowerMonitor
from llm_processor import MockLLMProcessor, LlamaProcessor
from scheduler import PowerAwareScheduler

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("main.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Setup command line arguments
parser = argparse.ArgumentParser(description='Solar-powered LLM system with delay-tolerant networking')
parser.add_argument('--model', help='Path to GGUF model file for llama.cpp')
parser.add_argument('--llama-cpp', default='./llama.cpp/main', help='Path to llama.cpp executable (usually named "main")')
parser.add_argument('--use-mock', action='store_true', help='Use mock LLM processor instead of real one')
parser.add_argument('--use-mock-power', action='store_true', help='Use mock power monitor instead of real TC66')
parser.add_argument('--immediate', action='store_true', help='Process prompts immediately without scheduling delays')
parser.add_argument('--serial-port', default='/dev/ttyACM0', help='Serial port for the TC66 power meter')
args = parser.parse_args()

# Initialize power monitor
# In immediate mode, set a higher initial solar output to ensure processing can happen
initial_solar = 50.0 if args.immediate else 30.0
initial_battery = 75.0

if args.use_mock_power:
    logger.info("Using mock power monitor (as requested)")
    power_monitor = MockPowerMonitor(initial_battery_level=initial_battery, max_solar_output=initial_solar)
else:
    # Try to initialize TC66PowerMonitor
    try:
        logger.info(f"Attempting to connect to TC66 power meter on {args.serial_port}")
        power_monitor = TC66PowerMonitor(
            serial_port=args.serial_port,
            initial_battery_level=initial_battery, 
            max_solar_output=initial_solar
        )
        # Test connection by getting a reading
        reading = power_monitor.get_current_power_reading()
        logger.info(f"Successfully initialized TC66PowerMonitor. Current reading: {reading}")
    except Exception as e:
        logger.error(f"Failed to initialize TC66PowerMonitor: {e}")
        logger.info("Falling back to mock power monitor")
        power_monitor = MockPowerMonitor(initial_battery_level=initial_battery, max_solar_output=initial_solar)
        
logger.info(f"Power monitor initialized: {type(power_monitor).__name__}")
request_queue = RequestQueue()

# Initialize LLM processor (mock or real)
if args.use_mock or not args.model:
    logger.info("Using mock LLM processor")
    llm_processor = MockLLMProcessor(power_monitor=power_monitor)
else:
    # Check if model file and llama.cpp executable exist
    if not os.path.exists(args.model):
        logger.error(f"Model file not found: {args.model}")
        logger.info("Falling back to mock LLM processor")
        llm_processor = MockLLMProcessor(power_monitor=power_monitor)
    elif not os.path.exists(args.llama_cpp):
        logger.error(f"llama.cpp executable not found: {args.llama_cpp}")
        logger.info("Falling back to mock LLM processor")
        llm_processor = MockLLMProcessor(power_monitor=power_monitor)
    else:
        logger.info(f"Using llama.cpp with model: {args.model}")
        logger.info(f"Using llama.cpp executable: {args.llama_cpp}")
        logger.info(f"Checking file permissions:")
        logger.info(f" - Model file exists: {os.path.exists(args.model)}")
        logger.info(f" - Model file size: {os.path.getsize(args.model) / (1024*1024):.2f} MB")
        logger.info(f" - Model file readable: {os.access(args.model, os.R_OK)}")
        logger.info(f" - llama.cpp exists: {os.path.exists(args.llama_cpp)}")
        logger.info(f" - llama.cpp executable: {os.access(args.llama_cpp, os.X_OK)}")
            
        try:
            # Check if llama.cpp executable can run
            version_check = subprocess.run(
                [args.llama_cpp, "--version"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                timeout=5
            )
            logger.info(f" - llama.cpp version check returncode: {version_check.returncode}")
            if version_check.stdout:
                logger.info(f" - llama.cpp stdout: {version_check.stdout.strip()}")
            if version_check.stderr:
                logger.info(f" - llama.cpp stderr: {version_check.stderr.strip()}")
        except Exception as e:
            logger.error(f" - llama.cpp version check error: {e}")
            
        try:
            # If the provided path is to llama.cpp file and not the executable, try to use 'main'
            if args.llama_cpp.endswith('/llama.cpp') and not os.access(args.llama_cpp, os.X_OK):
                correct_path = os.path.join(os.path.dirname(args.llama_cpp), 'main')
                if os.path.exists(correct_path) and os.access(correct_path, os.X_OK):
                    logger.warning(f"{args.llama_cpp} is not an executable. Using {correct_path} instead.")
                    args.llama_cpp = correct_path
                
            llm_processor = LlamaProcessor(
                model_path=args.model,
                power_monitor=power_monitor,
                llama_cpp_path=args.llama_cpp
            )
            logger.info("Successfully initialized LlamaProcessor")
        except Exception as e:
            logger.error(f"Error initializing LlamaProcessor: {e}")
            logger.info("\nPossible solutions:")
            logger.info("1. Make sure you're pointing to the compiled 'main' executable, not the 'llama.cpp' source file")
            logger.info("2. The correct command might be: python app.py --immediate --model /path/to/model.gguf --llama-cpp /home/matt/projects/llama.cpp/main")
            logger.info("3. Check if the executable has proper permissions (chmod +x)")
            logger.info("\nFalling back to mock LLM processor")
            llm_processor = MockLLMProcessor(power_monitor=power_monitor)

# Initialize scheduler with a callback to update conversation pages
def update_conversation_callback(conversation_id):
    """Callback function to update conversation page when a request completes."""
    if conversation_manager and conversation_id:
        logger.debug(f"Updating conversation page for ID: {conversation_id}")
        try:
            conversation_manager.update_conversation_page(conversation_id)
        except Exception as e:
            logger.error(f"Error updating conversation page: {e}")
    elif not conversation_id:
        logger.warning("Cannot update conversation: conversation_id is None")

scheduler = PowerAwareScheduler(
    power_monitor=power_monitor, 
    request_queue=request_queue, 
    llm_processor=llm_processor,
    callback_fn=update_conversation_callback,
    immediate_mode=args.immediate
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
    
    # Create a new conversation ID first
    import uuid
    conversation_id = str(uuid.uuid4())
    
    # Add prompt to scheduler queue with the conversation ID
    request_id, estimated_time = scheduler.enqueue_prompt(conversation_id, initial_prompt)
    
    # Create conversation 
    conversation_manager.create_new_conversation(
        initial_prompt, 
        estimated_time, 
        request_id,
        conversation_id
    )
    
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
    
    # Handle different power monitor types
    if isinstance(power_monitor, MockPowerMonitor):
        current = power_monitor.battery_level
        power_monitor.battery_level = min(100, current + amount)
        return jsonify({"status": "ok", "battery_level": power_monitor.battery_level, "monitor_type": "mock"})
    elif isinstance(power_monitor, TC66PowerMonitor):
        # For TC66, we can't directly manipulate the battery level because it's read from hardware
        # But we can report the current estimated level
        current_level = power_monitor.estimate_battery_level()
        return jsonify({
            "status": "info", 
            "message": "Cannot simulate charging with hardware power monitor",
            "battery_level": current_level,
            "monitor_type": "tc66"
        })
    else:
        return jsonify({"status": "error", "message": "Unknown power monitor type"})

@app.route('/simulate/discharge')
def simulate_discharge():
    """Simulate battery discharging."""
    amount = float(request.args.get('amount', 10))
    
    # Handle different power monitor types
    if isinstance(power_monitor, MockPowerMonitor):
        current = power_monitor.battery_level
        power_monitor.battery_level = max(0, current - amount)
        return jsonify({"status": "ok", "battery_level": power_monitor.battery_level, "monitor_type": "mock"})
    elif isinstance(power_monitor, TC66PowerMonitor):
        # For TC66, we can't directly manipulate the battery level
        current_level = power_monitor.estimate_battery_level()
        return jsonify({
            "status": "info", 
            "message": "Cannot simulate discharging with hardware power monitor",
            "battery_level": current_level,
            "monitor_type": "tc66"
        })
    else:
        return jsonify({"status": "error", "message": "Unknown power monitor type"})
        
@app.route('/api/power/readings')
def power_readings():
    """Get detailed power readings."""
    readings = power_monitor.get_current_power_reading()
    status = power_monitor.get_current_status()
    
    # Combine all available data
    result = {**readings, **status}
    
    # Add monitor type information
    if isinstance(power_monitor, MockPowerMonitor):
        result["monitor_type"] = "mock"
    elif isinstance(power_monitor, TC66PowerMonitor):
        result["monitor_type"] = "tc66"
    else:
        result["monitor_type"] = "unknown"
        
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)