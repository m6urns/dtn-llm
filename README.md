# Solar-Powered LLM System with Delay-Tolerant Networking

This project implements a solar-powered Large Language Model (LLM) service that utilizes principles of Delay-Tolerant Networking to handle requests when energy is available. Rather than failing during low-power periods, the system queues requests and processes them when sufficient power is available, providing users with estimated completion times.

Inspired by Low-tech Magazine's solar-powered website, this system demonstrates how AI services can operate sustainably even with intermittent power sources.

## Features

- **Power-Aware Scheduling**: Processes LLM requests based on available power
- **Request Queuing**: Persistent storage of requests until power is available
- **Static Web Interface**: Works with intermittent connectivity
- **Mock Components**: For testing without specialized hardware
- **Llama.cpp Integration**: For efficient LLM inference on low-powered devices

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

### Command Line Arguments

- `--model`: Path to GGUF model file
- `--llama-cpp`: Path to llama.cpp executable (default: ./llama.cpp/main)
- `--use-mock`: Use mock LLM processor instead of real one

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

## Current State and Future Development

See the `development_plan.txt` file for details on implemented features and future development plans.

## License

[MIT License](LICENSE)