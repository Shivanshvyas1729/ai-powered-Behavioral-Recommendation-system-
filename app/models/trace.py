from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class ExecutionTrace(BaseModel):
    trace_id: str = Field(..., description="Unique timestamp-based trace ID")
    user_id: int = Field(..., description="User ID who triggered the recommendation")
    timestamp: float = Field(..., description="Unix timestamp when trace started")
    
    t_total_ms: float = Field(0.0, description="Total execution time in milliseconds")
    t_vector_ms: float = Field(0.0, description="Vector DB retrieval time in milliseconds")
    t_llm_ms: float = Field(0.0, description="LLM generation time in milliseconds")
    
    candidates_found: int = Field(0, description="Number of candidate products retrieved")
    top_candidates: List[Dict[str, Any]] = Field(default_factory=list, description="Top retrieved products with similarity scores (if any)")
    
    narrative: str = Field("", description="Generated LLM narrative text")
    
    error_vector_db: Optional[str] = Field(None, description="Error message from vector DB if failed")
    error_llm: Optional[str] = Field(None, description="Error message from LLM if failed")
    success: bool = Field(False, description="True only if both Vector DB and LLM succeeded")
    
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata about models and environment")
