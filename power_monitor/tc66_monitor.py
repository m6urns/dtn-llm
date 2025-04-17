import time
import json
import os
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
import logging

from .base_monitor import BasePowerMonitor
from utils.monitor import TC66Monitor

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TC66PowerMonitor(BasePowerMonitor):
    """Power monitor implementation using TC66 USB-C power meter data."""
    
    def __init__(self, 
                 serial_port: str = '/dev/ttyACM0',
                 battery_capacity: float = 10000.0,  # mAh
                 battery_voltage: float = 3.7,      # Volts
                 initial_battery_level: float = 75.0,
                 base_consumption: float = 2.0,
                 max_solar_output: float = 30.0,
                 power_reading_cache_time: int = 5):  # seconds
        """Initialize the TC66 power monitor.
        
        Args:
            serial_port: The serial port where TC66 is connected
            battery_capacity: Battery capacity in mAh
            battery_voltage: Battery nominal voltage in V
            initial_battery_level: Initial battery level as percentage (0-100)
            base_consumption: Base system power consumption in Watts
            max_solar_output: Maximum expected solar panel output in Watts
            power_reading_cache_time: How long to cache power readings in seconds
        """
        self.serial_port = serial_port
        self.battery_capacity = battery_capacity
        self.battery_voltage = battery_voltage
        self.battery_level = initial_battery_level
        self.base_consumption = base_consumption
        self.max_solar_output = max_solar_output
        self.is_processing = False
        
        # Battery capacity in Watt-hours
        self.battery_capacity_wh = (battery_capacity / 1000) * battery_voltage
        
        # TC66 monitor
        self.tc66 = TC66Monitor(port=serial_port)
        
        # Cache for power readings to avoid excessive serial communication
        self.last_reading = None
        self.last_reading_time = 0
        self.power_reading_cache_time = power_reading_cache_time
        
        # Try initial connection
        self.connect()

        # Recent readings for estimating trends
        self.recent_readings = []
        self.max_recent_readings = 10
        
        # History file for solar output and battery trends
        self.history_file = "power_history.json"
        self.power_history = self.load_power_history()
        
        # Lock for thread safety
        self.lock = threading.Lock()
        
    def connect(self) -> bool:
        """Connect to the TC66 device."""
        try:
            success = self.tc66.connect()
            if success:
                logger.info(f"Successfully connected to TC66 at {self.serial_port}")
            else:
                logger.warning(f"Failed to connect to TC66 at {self.serial_port}")
            return success
        except Exception as e:
            logger.error(f"Error connecting to TC66: {e}")
            return False
    
    def load_power_history(self) -> Dict[str, Any]:
        """Load power history from file or create default."""
        default_history = {
            "daily_solar_patterns": {str(h): 0.0 for h in range(24)},
            "battery_discharge_rate": 0.5,  # % per hour under base load
            "last_updated": time.time()
        }
        
        if not os.path.exists(self.history_file):
            return default_history
            
        try:
            with open(self.history_file, "r") as f:
                history = json.load(f)
                return history
        except Exception as e:
            logger.error(f"Error loading power history: {e}")
            return default_history
    
    def save_power_history(self) -> None:
        """Save power history to file."""
        try:
            # Update last updated timestamp
            self.power_history["last_updated"] = time.time()
            
            with open(self.history_file, "w") as f:
                json.dump(self.power_history, f)
        except Exception as e:
            logger.error(f"Error saving power history: {e}")
    
    def update_power_history(self, reading: Dict[str, Any]) -> None:
        """Update power history with new reading."""
        with self.lock:
            # Update solar pattern for current hour
            current_hour = datetime.now().hour
            hour_key = str(current_hour)
            
            # Get solar output from reading (power is solar output in our system)
            solar_output = reading.get("power", 0.0)
            
            # Update with weighted average (95% old, 5% new)
            if hour_key in self.power_history["daily_solar_patterns"]:
                old_value = self.power_history["daily_solar_patterns"][hour_key]
                new_value = old_value * 0.95 + solar_output * 0.05
                self.power_history["daily_solar_patterns"][hour_key] = new_value
            else:
                self.power_history["daily_solar_patterns"][hour_key] = solar_output
            
            # Save every 10 readings
            if len(self.recent_readings) % 10 == 0:
                self.save_power_history()
    
    def get_current_power_reading(self) -> Dict[str, Any]:
        """Get current power reading from TC66.
        
        Returns:
            Dict with power data or fallback values if unable to read
        """
        # Check if we can use cached reading
        current_time = time.time()
        if (self.last_reading is not None and 
            current_time - self.last_reading_time < self.power_reading_cache_time):
            return self.last_reading
            
        try:
            # Try to read data from TC66
            data = self.tc66.read_data()
            
            if data is not None:
                # Use actual reading from TC66
                reading = {
                    "timestamp": int(current_time),
                    "voltage": data["voltage"],
                    "current": data["current"],
                    "power": data["power"],  # Solar output
                    "consumption": self.base_consumption if not self.is_processing else 5.0,  # Estimated consumption
                    "temperature": data["temperature"]
                }
                
                # Update cache
                self.last_reading = reading
                self.last_reading_time = current_time
                
                # Update recent readings
                with self.lock:
                    self.recent_readings.append(reading)
                    if len(self.recent_readings) > self.max_recent_readings:
                        self.recent_readings.pop(0)
                
                # Update power history
                self.update_power_history(reading)
                
                return reading
            else:
                logger.warning("Failed to read data from TC66, using fallback values")
        except Exception as e:
            logger.error(f"Error reading from TC66: {e}")
        
        # Fallback if reading failed
        if self.last_reading is not None:
            # Use last successful reading but with updated timestamp
            fallback = self.last_reading.copy()
            fallback["timestamp"] = int(current_time)
            return fallback
        else:
            # No previous reading, use mock values
            return {
                "timestamp": int(current_time),
                "voltage": 3.7 + (self.battery_level / 100 * 0.8),  # 3.7-4.5V range
                "current": 1.0 if self.is_processing else 0.4,
                "power": self.estimate_solar_output_for_hour(datetime.now().hour),
                "consumption": self.base_consumption if not self.is_processing else 5.0,
                "temperature": 25.0
            }
    
    def estimate_battery_level(self) -> float:
        """Estimate battery level based on voltage and usage history."""
        # Get current reading
        reading = self.get_current_power_reading()
        voltage = reading["voltage"]
        
        # Simple voltage-based estimation
        # 3.3V (0%) to 4.2V (100%) for a typical Li-ion cell
        min_voltage = 3.3
        max_voltage = 4.2
        
        # Clamp voltage to range
        clamped_voltage = max(min_voltage, min(max_voltage, voltage))
        
        # Calculate percentage
        percentage = (clamped_voltage - min_voltage) / (max_voltage - min_voltage) * 100
        
        # Return rounded value
        return round(percentage, 1)
    
    def get_solar_output(self) -> float:
        """Get current solar panel output in Watts."""
        # The power reading from TC66 is the current solar output
        reading = self.get_current_power_reading()
        return reading["power"]
    
    def estimate_solar_output_for_hour(self, hour: int) -> float:
        """Estimate solar output for a specific hour based on history."""
        hour_key = str(hour)
        
        # Use historical data if available
        if hour_key in self.power_history["daily_solar_patterns"]:
            return self.power_history["daily_solar_patterns"][hour_key]
        
        # Fallback to time-of-day estimation
        if 6 <= hour <= 18:  # Daylight hours
            hour_factor = 1 - abs((hour - 12) / 6)  # 0 to 1, peaking at noon
            solar_estimate = self.max_solar_output * hour_factor
        else:
            solar_estimate = 0.0  # Night time
            
        return solar_estimate
    
    def predict_future_availability(self, hours_ahead: int = 24) -> List[Dict[str, Any]]:
        """Predict power availability for upcoming hours."""
        predictions = []
        
        current_hour = datetime.now().hour
        current_battery = self.battery_level
        
        for hour in range(hours_ahead):
            forecast_hour = (current_hour + hour) % 24
            
            # Get solar estimate for this hour
            solar_estimate = self.estimate_solar_output_for_hour(forecast_hour)
            
            # Estimate power consumption
            consumption_estimate = self.base_consumption
            
            # Calculate net power flow
            net_power = solar_estimate - consumption_estimate
            
            # Estimate battery change
            if net_power > 0:
                # Charging: reduced efficiency as battery fills up
                charge_efficiency = 0.85 - (0.2 * current_battery / 100)
                energy_in = net_power * charge_efficiency
                battery_change = (energy_in / self.battery_capacity_wh) * 100
            else:
                # Discharging
                battery_change = (net_power / self.battery_capacity_wh) * 100
            
            # Update battery level for next hour
            current_battery += battery_change
            current_battery = max(0, min(100, current_battery))
            
            predictions.append({
                "hour": forecast_hour,
                "solar_output": solar_estimate,
                "battery_level": current_battery,
                "processing_capable": current_battery > 30 and solar_estimate > self.base_consumption
            })
            
        return predictions
    
    def can_process_request(self, estimated_power_requirement: float) -> bool:
        """Determine if there's enough power to process a request."""
        # Get current readings
        battery_level = self.estimate_battery_level()
        solar_output = self.get_solar_output()
        
        # Determine if we have enough power
        # Require at least 30% battery and either:
        # 1. Solar output is greater than the requirement, or
        # 2. Battery level is high enough (>70%) to handle short processing
        return (battery_level > 30 and 
                (solar_output >= estimated_power_requirement or battery_level > 70))
    
    def get_current_status(self) -> Dict[str, Any]:
        """Get complete power status information."""
        readings = self.get_current_power_reading()
        battery_level = self.estimate_battery_level()
        
        return {
            "battery_level": battery_level,
            "solar_output": readings["power"],
            "power_consumption": readings["consumption"],
            "temperature": readings["temperature"],
            "timestamp": readings["timestamp"],
            "voltage": readings["voltage"],
            "current": readings["current"]
        }
    
    def set_processing_state(self, is_processing: bool) -> None:
        """Set whether the system is currently processing a request."""
        self.is_processing = is_processing