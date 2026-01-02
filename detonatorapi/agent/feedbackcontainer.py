from dataclasses import dataclass
from typing import Optional, Generic, TypeVar

T = TypeVar('T')

@dataclass
class FeedbackContainer(Generic[T]):
    """A result type that can represent success or failure with optional value and error message."""
    success: bool
    value: Optional[T] = None
    error_message: Optional[str] = None
    
    def __bool__(self) -> bool:
        """Allow usage in if statements: if result: ..."""
        return self.success
    
    @classmethod
    def ok(cls, value: Optional[T] = None) -> 'FeedbackContainer[T]':
        """Create a successful result."""
        return cls(success=True, value=value)
    
    @classmethod
    def error(cls, error_message: str) -> 'FeedbackContainer[T]':
        """Create a failed result with error message."""
        return cls(success=False, error_message=error_message)
    
    def unwrap(self) -> T:
        """Get the value, raising an exception if the result is an error."""
        if not self.success:
            raise ValueError(f"Cannot unwrap error result: {self.error_message}")
        if self.value is None:
            raise ValueError("Cannot unwrap None value")
        return self.value
