import time
import random
from datetime import datetime
from typing import Dict, List, Any, Optional, Union

from .base_monitor import BasePowerMonitor


class MockPowerMonitor(BasePowerMonitor):
    """Mock power monitor for testing with simulated solar power and battery."""
    
    def __init__(self, 
                 initial_battery_level: float = 75.0,
                 max_solar_output: float = 30.0,
                 base_consumption: float = 2.0,
                 processing_consumption: float = 5.0):
        """Initialize the mock power monitor with configurable parameters.
        
        Args:
            initial_battery_level: Initial battery level percentage (0-100)
            max_solar_output: Maximum solar panel output in Watts at peak time
            base_consumption: Base system power consumption in Watts
            processing_consumption: Additional power consumption when processing
        """
        self.battery_level = initial_battery_level
        self.max_solar_output = max_solar_output
        self.base_consumption = base_consumption
        self.processing_consumption = processing_consumption
        self.is_processing = False
        
    def get_current_power_reading(self) -> Dict[str, Any]:
        """Get simulated power readings."""
        current_hour = datetime.now().hour
        
        # Simulate solar output based on time of day
        if 6 <= current_hour <= 18:  # Daylight hours
            hour_factor = 1 - abs((current_hour - 12) / 6)  # 0 to 1, peaking at noon
            cloud_factor = random.uniform(0.7, 1.0)  # Random cloud cover
            solar_output = self.max_solar_output * hour_factor * cloud_factor
        else:
            solar_output = 0  # Night time
            
        # Calculate simulated consumption
        power_consumption = self.processing_consumption if self.is_processing else self.base_consumption
        
        return {
            "timestamp": int(time.time()),
            "voltage": 3.7 + (self.battery_level / 100 * 0.8),  # 3.7-4.5V range
            "current": 1.0 if self.is_processing else 0.4,  # A
            "power": solar_output,
            "consumption": power_consumption,
            "temperature": 25 + random.uniform(-2, 2)  # Slight temperature variance
        }
    
    def estimate_battery_level(self) -> float:
        """Return the current simulated battery level."""
        return self.battery_level
    
    def get_solar_output(self) -> float:
        """Get current simulated solar panel output."""
        return self.get_current_power_reading()["power"]
    
    def predict_future_availability(self, hours_ahead: int = 24) -> List[Dict[str, Any]]:
        """Predict power availability for upcoming hours."""
        predictions = []
        
        current_hour = datetime.now().hour
        battery_level = self.battery_level
        
        for hour in range(hours_ahead):
            forecast_hour = (current_hour + hour) % 24
            
            # Simulate solar output based on time of day
            if 6 <= forecast_hour <= 18:  # Daylight hours
                hour_factor = 1 - abs((forecast_hour - 12) / 6)
                # Weather gets more unpredictable further ahead
                variance = min(0.3, hour * 0.01)
                cloud_factor = random.uniform(0.7 - variance, 1.0)
                solar_estimate = self.max_solar_output * hour_factor * cloud_factor
            else:
                solar_estimate = 0  # Night time
            
            # Simulate battery charge/discharge
            consumption_estimate = self.base_consumption
            net_power = solar_estimate - consumption_estimate
            
            # Update simulated battery level
            battery_level += net_power * 0.2  # Simple approximation
            battery_level = max(0, min(100, battery_level))
            
            predictions.append({
                "hour": forecast_hour,
                "solar_output": solar_estimate,
                "battery_level": battery_level,
                "processing_capable": battery_level > 30 and solar_estimate > self.base_consumption
            })
            
        return predictions
    
    def can_process_request(self, estimated_power_requirement: float) -> bool:
        """Determine if there's enough power to process a request."""
        current_reading = self.get_current_power_reading()
        battery_level = self.battery_level
        
        # Simple rule: we need at least 30% battery and more solar input than the requirement
        return battery_level > 30 and current_reading["power"] > estimated_power_requirement
    
    def get_current_status(self) -> Dict[str, Any]:
        """Get complete power status information."""
        readings = self.get_current_power_reading()
        
        return {
            "battery_level": self.battery_level,
            "solar_output": readings["power"],
            "power_consumption": readings["consumption"],
            "temperature": readings["temperature"],
            "timestamp": readings["timestamp"]
        }
    
    def set_processing_state(self, is_processing: bool) -> None:
        """Set whether the system is currently processing a request.
        
        Args:
            is_processing: True if processing, False otherwise
        """
        self.is_processing = is_processing
        
    def simulate_battery_change(self, elapsed_time: Union[int, float], power_used: float) -> None:
        """Simulate battery discharge based on time elapsed and power used.
        
        Args:
            elapsed_time: Time in seconds
            power_used: Power used in Watts
        """
        # Simple battery model: assume 10000 mAh battery at 3.7V (37 Wh)
        battery_capacity_wh = 37.0
        
        # Calculate energy used in Watt-hours
        energy_used = power_used * (elapsed_time / 3600)
        
        # Convert to percentage
        percentage_used = (energy_used / battery_capacity_wh) * 100
        
        # Update battery level
        self.battery_level -= percentage_used
        self.battery_level = max(0, min(100, self.battery_level))
        
    def simulate_time_passing(self, hours: float = 1.0) -> None:
        """Simulate the passage of time and update battery level.
        
        Args:
            hours: Number of hours to simulate
        """
        current_hour = datetime.now().hour
        end_hour = (current_hour + int(hours)) % 24
        fractional_hour = hours - int(hours)
        
        # Simulate each hour individually for more accuracy
        for h in range(int(hours)):
            sim_hour = (current_hour + h) % 24
            
            # Get solar output for this hour
            if 6 <= sim_hour <= 18:
                hour_factor = 1 - abs((sim_hour - 12) / 6)
                cloud_factor = random.uniform(0.7, 1.0)
                solar_output = self.max_solar_output * hour_factor * cloud_factor
            else:
                solar_output = 0
                
            # Calculate net power flow
            consumption = self.base_consumption
            net_power = solar_output - consumption
            
            # Update battery (positive net power charges, negative discharges)
            energy_change = net_power * 1.0  # 1 hour
            
            # Convert to percentage (assuming 37 Wh battery)
            battery_capacity_wh = 37.0
            percentage_change = (energy_change / battery_capacity_wh) * 100
            
            self.battery_level += percentage_change
            self.battery_level = max(0, min(100, self.battery_level))
        
        # Handle fractional hour
        if fractional_hour > 0:
            if 6 <= end_hour <= 18:
                hour_factor = 1 - abs((end_hour - 12) / 6)
                cloud_factor = random.uniform(0.7, 1.0)
                solar_output = self.max_solar_output * hour_factor * cloud_factor
            else:
                solar_output = 0
                
            consumption = self.base_consumption
            net_power = solar_output - consumption
            
            energy_change = net_power * fractional_hour
            battery_capacity_wh = 37.0
            percentage_change = (energy_change / battery_capacity_wh) * 100
            
            self.battery_level += percentage_change
            self.battery_level = max(0, min(100, self.battery_level))