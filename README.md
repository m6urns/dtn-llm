# Solar-Powered LLM System with Delay-Tolerant Networking

This project implements a solar-powered Large Language Model (LLM) service that utilizes principles of Delay-Tolerant Networking to handle requests when energy is available. Rather than failing during low-power periods, the system queues requests and processes them when sufficient power is available, providing users with estimated completion times.

Inspired by Low-tech Magazine's solar-powered website, this system demonstrates how AI services can operate sustainably even with intermittent power sources.

## Features

- **Power-Aware Scheduling**: Processes LLM requests based on available power
- **Request Queuing**: Persistent storage of requests until power is available
- **Static Web Interface**: Works with intermittent connectivity
- **Mock Components**: For testing without specialized hardware
- **Llama.cpp Integration**: For efficient LLM inference on low-powered devices
- **TC66 Power Monitoring**: Real-time power monitoring via USB-C meter

## Setup

### Prerequisites

- Python 3.9+
- Llama.cpp (for real LLM processing)
- GGUF model file (e.g., llama-2-7b.Q4_K_M.gguf)
- TC66C USB power monitor (for real power monitoring, optional)

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/username/dtn-llm.git
   cd dtn-llm
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Install and build llama.cpp:
   ```
   git clone https://github.com/ggerganov/llama.cpp.git
   cd llama.cpp
   make
   ```

4. Download a GGUF model file (e.g., from HuggingFace)

## Running the Application

### Using Mock Components (for testing)

```
python app.py --use-mock
```

### Using a Real LLM with llama.cpp

```
python app.py --model /path/to/model.gguf --llama-cpp /path/to/llama.cpp/main
```

### Using Real TC66 Power Monitor

```
python app.py --model /path/to/model.gguf --llama-cpp /path/to/llama.cpp/main --serial-port /dev/ttyACM0
```

Note: The TC66 power monitor will be used by default if available. Use `--use-mock-power` to force using the mock monitor.

### Command Line Arguments

- `--model`: Path to GGUF model file
- `--llama-cpp`: Path to llama.cpp executable (default: ./llama.cpp/main)
- `--use-mock`: Use mock LLM processor instead of real one
- `--use-mock-power`: Use mock power monitor instead of real TC66
- `--serial-port`: Serial port for the TC66 power meter (default: /dev/ttyACM0)
- `--immediate`: Process prompts immediately without scheduling delays

## System Architecture

```
                                                              
  Web Interface    �    $ Request Scheduler�    $ Power Monitor 
  - Static content       - Queue manager        - TC66C       
  - Status display       - Time estimator       - Battery sim 
        ,                       ,                     ,       
                                                          
                                  �                        
                                                         
                       �  LLM Processor   �              
                           - llama.cpp     
                           - Result storage
                                           
```

## Project Structure

- `app.py`: Main Flask application
- `queue/`: Request queue management
- `scheduler/`: Power-aware scheduler
- `power_monitor/`: Power monitoring system
- `llm_processor/`: LLM processing modules
- `web/`: Web interface components
- `static/`: Static files and generated conversations
- `templates/`: HTML templates
- `tests/`: Unit tests
- `utils/`: Utility scripts including TC66 monitor

## Development

### Running Tests

```
pytest tests/
```

### Running a Specific Test

```
pytest tests/test_file.py::test_function
```

### Linting and Type Checking

```
flake8 .
mypy .
```

## API Endpoints

The application provides the following API endpoints:

### System Status

- **URL:** `/api/status`
- **Method:** GET
- **Description:** Get the current system status
- **Response:**
  ```json
  {
    "battery_level": 75.5,
    "solar_output": 25.3,
    "queue_length": 2,
    "processing_active": true,
    "timestamp": 1713530400
  }
  ```

### Request Status

- **URL:** `/api/request/<request_id>`
- **Method:** GET
- **Description:** Get status of a specific request
- **Response:**
  ```json
  {
    "id": "1234abcd",
    "status": "queued",
    "prompt": "Tell me about solar power",
    "queue_position": 2,
    "estimated_completion": "2025-04-17T15:30:00"
  }
  ```

### Power Readings

- **URL:** `/api/power/readings`
- **Method:** GET
- **Description:** Get detailed power monitor readings
- **Response:**
  ```json
  {
    "timestamp": 1713530400,
    "voltage": 3.85,
    "current": 0.5,
    "power": 25.3,
    "temperature": 28.5,
    "battery_level": 75.5,
    "solar_output": 25.3,
    "power_consumption": 2.0,
    "monitor_type": "tc66"
  }
  ```

### Simulation Endpoints (Testing Only)

- **URL:** `/simulate/charge`
- **Method:** GET
- **Parameters:** `amount` (optional, default: 10)
- **Description:** Simulate battery charging (mock monitor only)

- **URL:** `/simulate/discharge`
- **Method:** GET
- **Parameters:** `amount` (optional, default: 10)
- **Description:** Simulate battery discharging (mock monitor only)

## Current State and Future Development

See the `development_plan.txt` file for details on implemented features and future development plans.

## License

[MIT License](LICENSE)