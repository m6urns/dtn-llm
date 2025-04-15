from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseLLMProcessor(ABC):
    """Base class for LLM processing implementations."""
    
    @abstractmethod
    def generate_response(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """Generate a response to the prompt.
        
        Args:
            prompt: The input prompt text
            max_tokens: Optional maximum number of tokens to generate
            
        Returns:
            str: The generated response
        """
        pass
    
    @abstractmethod
    def determine_max_tokens(self) -> int:
        """Determine maximum response length based on power availability.
        
        Returns:
            int: Maximum number of tokens to generate
        """
        pass