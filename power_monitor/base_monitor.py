from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Any, Optional


class BasePowerMonitor(ABC):
    """Base class for power monitoring implementations."""
    
    @abstractmethod
    def get_current_power_reading(self) -> Dict[str, Any]:
        """Read current power data.
        
        Returns:
            Dict with at least the following keys:
            - timestamp: int (Unix timestamp)
            - voltage: float (Volts)
            - current: float (Amps)
            - power: float (Watts)
            - temperature: float (Celsius)
        """
        pass
    
    @abstractmethod
    def estimate_battery_level(self) -> float:
        """Estimate current battery level as a percentage (0-100).
        
        Returns:
            float: Battery level percentage
        """
        pass
    
    @abstractmethod
    def get_solar_output(self) -> float:
        """Get current solar panel output in Watts.
        
        Returns:
            float: Solar output in Watts
        """
        pass
    
    @abstractmethod
    def predict_future_availability(self, hours_ahead: int = 24) -> List[Dict[str, Any]]:
        """Predict power availability for upcoming hours.
        
        Args:
            hours_ahead: Number of hours to predict ahead
            
        Returns:
            List of dictionaries, each containing:
            - hour: int (Hour of day 0-23)
            - solar_output: float (Predicted Watts)
            - battery_level: float (Predicted percentage)
            - processing_capable: bool (Whether processing is possible)
        """
        pass
    
    @abstractmethod
    def can_process_request(self, estimated_power_requirement: float) -> bool:
        """Determine if there's enough power to process a request.
        
        Args:
            estimated_power_requirement: Estimated power needed in Watts
            
        Returns:
            bool: True if request can be processed, False otherwise
        """
        pass
    
    @abstractmethod
    def get_current_status(self) -> Dict[str, Any]:
        """Get complete power status information.
        
        Returns:
            Dict with at least the following keys:
            - battery_level: float (percentage)
            - solar_output: float (Watts)
            - power_consumption: float (Watts)
            - temperature: float (Celsius)
            - timestamp: int (Unix timestamp)
        """
        pass