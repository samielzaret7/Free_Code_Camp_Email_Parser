from pydantic import BaseModel
from typing import List, Optional

class FCCItem(BaseModel):
    name: str
    link: Optional[str] = None
    time: Optional[str] = None
    description: Optional[str] = None

    
    categories: Optional[List[str]] = None
    category_confidence: Optional[float] = None
    suggested_new_category: Optional[str] = None

    date_added: Optional[str] = None  

class ParseResult(BaseModel):
    items: List[FCCItem] = []
