#!/usr/bin/env python3
"""
Test script for TC66 power monitor.
This script tests the TC66 power monitor implementation.
"""

import argparse
import time
import logging
from datetime import datetime
from power_monitor import TC66PowerMonitor, MockPowerMonitor

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Main function to test the TC66 power monitor."""
    parser = argparse.ArgumentParser(description='Test TC66 power monitor')
    parser.add_argument('--port', default='/dev/ttyACM0', help='Serial port for the TC66 device')
    parser.add_argument('--interval', type=float, default=2.0, help='Sampling interval in seconds')
    parser.add_argument('--duration', type=int, default=30, help='Test duration in seconds')
    parser.add_argument('--use-mock', action='store_true', help='Use mock monitor instead of TC66')
    args = parser.parse_args()

    logger.info("Starting power monitor test")
    
    try:
        if args.use_mock:
            logger.info("Initializing mock power monitor")
            monitor = MockPowerMonitor(initial_battery_level=75.0, max_solar_output=30.0)
        else:
            logger.info(f"Initializing TC66 power monitor on port {args.port}")
            monitor = TC66PowerMonitor(serial_port=args.port)

        # Test connection by getting a reading
        logger.info("Testing initial power reading...")
        reading = monitor.get_current_power_reading()
        logger.info(f"Initial power reading: {reading}")

        # Run continuous monitoring loop
        logger.info(f"Starting monitoring loop (interval: {args.interval}s, duration: {args.duration}s)")
        start_time = time.time()
        
        print(f"{'Time':20} | {'Voltage (V)':12} | {'Current (A)':12} | {'Power (W)':12} | {'Temperature (°C)':15} | {'Battery (%)':12}")
        print("-" * 90)
        
        while time.time() - start_time < args.duration:
            # Get power reading
            reading = monitor.get_current_power_reading()
            status = monitor.get_current_status()
            
            # Current time
            current_time = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            
            # Print formatted data
            print(f"{current_time:20} | {reading['voltage']:12.3f} | {reading['current']:12.3f} | {reading['power']:12.3f} | {reading['temperature']:15.1f} | {status['battery_level']:12.1f}")
            
            # Sleep for interval
            time.sleep(args.interval)
        
        # Test prediction
        logger.info("Testing power availability prediction...")
        predictions = monitor.predict_future_availability(hours_ahead=12)
        
        print("\nPower availability predictions for the next 12 hours:")
        print(f"{'Hour':5} | {'Solar Output (W)':15} | {'Battery Level (%)':18} | {'Processing Capable':18}")
        print("-" * 65)
        
        for pred in predictions:
            print(f"{pred['hour']:5} | {pred['solar_output']:15.2f} | {pred['battery_level']:18.2f} | {pred['processing_capable']:18}")
        
        logger.info("Test completed successfully")
    
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Error during test: {e}", exc_info=True)

if __name__ == "__main__":
    main()