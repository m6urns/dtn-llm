import os
import uuid
from datetime import datetime
import json

class ConversationManager:
    def __init__(self, static_pages_dir="static/conversations", request_queue=None, power_monitor=None):
        self.pages_dir = static_pages_dir
        self.request_queue = request_queue
        self.power_monitor = power_monitor
        
        # Create directory if it doesn't exist
        os.makedirs(self.pages_dir, exist_ok=True)
        
    def create_new_conversation(self, initial_prompt, estimated_time=None, request_id=None):
        """Create a new conversation with initial prompt"""
        # Generate unique conversation ID if not provided
        conversation_id = str(uuid.uuid4())
        
        # Create directory for this conversation
        conversation_dir = f"{self.pages_dir}/{conversation_id}"
        os.makedirs(conversation_dir, exist_ok=True)
        
        # Generate initial waiting page if we have power monitor and request data
        if self.power_monitor and estimated_time and request_id:
            self.generate_waiting_page(conversation_id, initial_prompt, request_id, estimated_time)
        else:
            # Create a basic page without power info
            self.generate_basic_page(conversation_id, initial_prompt)
        
        return conversation_id
    
    def generate_basic_page(self, conversation_id, prompt):
        """Generate a basic HTML page for a new conversation without power info"""
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Solar LLM Conversation</title>
            <style>
                body {{ font-family: system-ui, sans-serif; margin: 2em; max-width: 800px; line-height: 1.6; }}
                .prompt, .response, .status {{
                    margin: 1em 0;
                    padding: 1em;
                    border-radius: 3px;
                }}
                .prompt {{ background: #f0f0f0; }}
                .status {{ background: #fff8e1; }}
            </style>
        </head>
        <body>
            <h1>Solar LLM Conversation</h1>
            
            <h2>Your prompt is in queue</h2>
            <div class="prompt">
                <p><strong>You:</strong> {prompt}</p>
            </div>
            
            <div class="status">
                <p>Your request has been queued.</p>
                <p>This page will automatically refresh when the response is ready.</p>
            </div>
            
            <p>This page will automatically refresh. You can also bookmark it and come back later.</p>
            <p><a href="/">Return to home page</a></p>
        </body>
        </html>
        """
        
        # Write HTML to file
        with open(f"{self.pages_dir}/{conversation_id}/index.html", 'w') as f:
            f.write(html_content)
    
    def generate_waiting_page(self, conversation_id, prompt, request_id, estimated_time):
        """Generate HTML page showing waiting status with power information"""
        # Get current power status
        power_status = self.power_monitor.get_current_status() if self.power_monitor else {
            'battery_level': 0, 'solar_output': 0
        }
        
        queue_position = self.request_queue.get_queue_position(request_id) if self.request_queue else None
        
        # Create HTML with waiting status
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Solar LLM Conversation</title>
            <meta http-equiv="refresh" content="60"> <!-- Auto-refresh every minute -->
            <style>
                body {{ font-family: system-ui, sans-serif; margin: 2em; max-width: 800px; line-height: 1.6; }}
                .battery-status {{ 
                    height: 20px; 
                    background: linear-gradient(to right, #4CAF50 {power_status['battery_level']}%, #f0f0f0 0%);
                    margin-bottom: 1em;
                    border-radius: 3px;
                }}
                .prompt, .response, .status {{
                    margin: 1em 0;
                    padding: 1em;
                    border-radius: 3px;
                }}
                .prompt {{ background: #f0f0f0; }}
                .status {{ background: #fff8e1; }}
            </style>
        </head>
        <body>
            <h1>Solar LLM Conversation</h1>
            <div class="battery-status" title="Battery level: {power_status['battery_level']}%"></div>
            
            <h2>Your prompt is in queue</h2>
            <div class="prompt">
                <p><strong>You:</strong> {prompt}</p>
            </div>
            
            <div class="status">
                <p>Estimated response time: {estimated_time.strftime('%Y-%m-%d %H:%M') if hasattr(estimated_time, 'strftime') else estimated_time}</p>
                <p>Current queue position: {queue_position if queue_position else 'Unknown'}</p>
                <p>Current solar output: {power_status.get('solar_output', 0):.2f}W</p>
                <p>Battery level: {power_status.get('battery_level', 0):.1f}%</p>
            </div>
            
            <p>This page will automatically refresh. You can also bookmark it and come back later.</p>
            <p><a href="/">Return to home page</a></p>
        </body>
        </html>
        """
        
        # Write HTML to file
        with open(f"{self.pages_dir}/{conversation_id}/index.html", 'w') as f:
            f.write(html_content)
    
    def update_conversation_page(self, conversation_id):
        """Update conversation page with completed responses"""
        # Get all requests for this conversation
        requests = self.request_queue.get_conversation_requests(conversation_id) if self.request_queue else []
        
        # Get current power status
        power_status = self.power_monitor.get_current_status() if self.power_monitor else {
            'battery_level': 0, 'solar_output': 0
        }
        
        # Build conversation HTML
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Solar LLM Conversation</title>
            <style>
                body {{ font-family: system-ui, sans-serif; margin: 2em; max-width: 800px; line-height: 1.6; }}
                .battery-status {{ 
                    height: 20px; 
                    background: linear-gradient(to right, #4CAF50 {power_status.get('battery_level', 0)}%, #f0f0f0 0%);
                    margin-bottom: 1em;
                    border-radius: 3px;
                }}
                .prompt, .response, .status {{
                    margin: 1em 0;
                    padding: 1em;
                    border-radius: 3px;
                }}
                .prompt {{ background: #f0f0f0; }}
                .response {{ background: #e1f5fe; }}
                .status {{ background: #fff8e1; }}
                form {{ margin: 2em 0; }}
                textarea {{ width: 100%; height: 100px; padding: 0.5em; font-family: inherit; }}
                button {{ padding: 0.5em 1em; background: #4CAF50; color: white; border: none; border-radius: 3px; }}
            </style>
        </head>
        <body>
            <h1>Solar LLM Conversation</h1>
            <div class="battery-status" title="Battery level: {power_status.get('battery_level', 0)}%"></div>
            
            <div class="power-info">
                <p>Current solar output: {power_status.get('solar_output', 0):.2f}W</p>
                <p>Battery level: {power_status.get('battery_level', 0):.1f}%</p>
            </div>
        """
        
        # Add conversation exchanges
        for request in requests:
            html_content += f"""
            <div class="prompt">
                <p><strong>You:</strong> {request['prompt']}</p>
            </div>
            """
            
            if request['status'] == 'completed' and request['response']:
                html_content += f"""
                <div class="response">
                    <p><strong>AI:</strong> {request['response']}</p>
                </div>
                """
            elif request['status'] == 'processing':
                html_content += f"""
                <div class="status">
                    <p>Processing your request...</p>
                    <p>This page will automatically refresh when the response is ready.</p>
                </div>
                <meta http-equiv="refresh" content="30">
                """
            elif request['status'] == 'queued':
                # Try to parse estimated completion time
                try:
                    if isinstance(request['estimated_completion'], str):
                        estimated_time = datetime.fromisoformat(request['estimated_completion'])
                    else:
                        estimated_time = request['estimated_completion']
                    time_str = estimated_time.strftime('%Y-%m-%d %H:%M')
                except (ValueError, AttributeError):
                    time_str = "Unknown"
                
                html_content += f"""
                <div class="status">
                    <p>Your request is queued.</p>
                    <p>Estimated response time: {time_str}</p>
                    <p>This page will automatically refresh when the response is ready.</p>
                </div>
                <meta http-equiv="refresh" content="60">
                """
        
        # Add form for new prompt if most recent request is completed or if there are no requests
        if not requests or requests[-1]['status'] == 'completed':
            html_content += f"""
            <form action="/submit" method="post">
                <input type="hidden" name="conversation_id" value="{conversation_id}">
                <textarea name="prompt" placeholder="Enter your next prompt..."></textarea>
                <button type="submit">Submit</button>
            </form>
            """
        
        html_content += """
            <p><a href="/">Return to home page</a></p>
            <p><a href="/download/{conversation_id}">Download conversation</a></p>
        </body>
        </html>
        """
        
        # Write HTML to file
        with open(f"{self.pages_dir}/{conversation_id}/index.html", 'w') as f:
            f.write(html_content)
            
    def get_conversation_path(self, conversation_id):
        """Get the path to a conversation's HTML file"""
        return f"{self.pages_dir}/{conversation_id}/index.html"
    
    def conversation_exists(self, conversation_id):
        """Check if a conversation exists"""
        return os.path.exists(f"{self.pages_dir}/{conversation_id}/index.html")