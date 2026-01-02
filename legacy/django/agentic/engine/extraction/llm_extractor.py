"""
LLM Extraction Engine using LangChain and Pydantic.
"""

import os
from typing import Any, Dict, List, Optional
from decimal import Decimal
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from agentic_core.models.documents import ExtractedDocument, DocumentType, ExtractionConfidence

class ExtractionSchema(BaseModel):
    """Schema for structured LLM extraction."""
    vendor_name: str = Field(description="Name of the vendor or payee")
    total_amount: Decimal = Field(description="Grand total amount on the document")
    currency: str = Field(default="USD", description="Currency code (e.g., USD, CAD)")
    document_date: Optional[str] = Field(None, description="Date on the document in YYYY-MM-DD format")
    document_type: str = Field(description="Type of document (receipt, invoice, bank_statement, etc.)")
    line_items: List[Dict[str, Any]] = Field(default_factory=list, description="Individual line items if present")

EXTRACTION_PROMPT = """
Extract structured information from the following document text.
If any field is missing, provide your best guess or null if impossible.

Document Text:
{text}

{format_instructions}
"""

class LLMExtractor:
    def __init__(self, model_name: str = "gpt-4o-mini"):
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            # Fallback to DeepSeek if available
            self.api_key = os.environ.get("COMPANION_LLM_API_KEY")
            self.model = ChatOpenAI(
                model="deepseek-chat",
                openai_api_key=self.api_key,
                openai_api_base="https://api.deepseek.com/v1"
            )
        else:
            self.model = ChatOpenAI(model=model_name, openai_api_key=self.api_key)
            
        self.parser = PydanticOutputParser(pydantic_object=ExtractionSchema)
        self.prompt = ChatPromptTemplate.from_template(EXTRACTION_PROMPT)

    def extract(self, text: str) -> ExtractedDocument:
        """Extract structured data from text."""
        try:
            chain = self.prompt | self.model | self.parser
            result = chain.invoke({
                "text": text,
                "format_instructions": self.parser.get_format_instructions()
            })
            
            # Map ExtractionSchema to ExtractedDocument
            return ExtractedDocument(
                source_document_id="pending", # To be filled by workflow
                vendor_name=result.vendor_name,
                total_amount=result.total_amount,
                currency=result.currency,
                document_date=result.document_date,
                document_type=result.document_type,
                line_items=result.line_items, # Note: Needs mapping to ExtractedLineItem if robust
                confidence=ExtractionConfidence.HIGH,
                extraction_model=self.model.model_name
            )
        except Exception as e:
            # Fallback or error logging
            return ExtractedDocument(
                source_document_id="failed",
                total_amount=Decimal("0"),
                extraction_warnings=[f"LLM Extraction failed: {str(e)}"],
                confidence=ExtractionConfidence.LOW
            )
