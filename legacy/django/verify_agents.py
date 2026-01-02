"""
Integration test and verification for agent system improvements.
"""

import os
import django
import asyncio
from datetime import datetime

# Setup Django for standalone use
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'minibooks_project.settings')
django.setup()

from agentic.workflows.steps.receipts_pipeline import build_receipts_workflow
from agentic.agents.evaluation.evaluator_agent import EvaluatorAgent
from agentic.memory.vector_store import VectorStore, MemoryEntry

async def run_verification():
    print("🚀 Starting Agent System Verification...")
    
    # 1. Test Vector Memory
    print("\n[Phase 3] Testing Vector Memory...")
    store = VectorStore(store_path="agentic/memory/test_store.pkl")
    entry = MemoryEntry(content="The user always categorizes Starbucks as Office Supplies.", metadata={"user_id": 1})
    store.add(entry)
    results = store.search_by_text("Where does Starbucks go?")
    print(f"Memory Recall Result: {results[0][0].content if results else 'None'}")
    
    # 2. Test Receipts Workflow (Phases 1, 2, 4)
    print("\n[Phases 1, 2, 4] Testing Integrated Receipts Workflow...")
    # Mock uploaded files
    context = {
        "uploaded_files": [
            {"filename": "office-depot.pdf", "content": "Office Depot receipt for $89.99"}
        ]
    }
    
    workflow = build_receipts_workflow()
    print(f"Running workflow: {workflow.name}...")
    result = workflow.run(context)
    
    print(f"Workflow Status: {result.status}")
    if "extracted_documents" in result.artifacts:
        ext = result.artifacts["extracted_documents"][0]
        print(f"Extracted Vendor: {ext.get('vendor_name')}")
        print(f"Extracted Amount: {ext.get('total_amount')}")

    # 3. Test Evaluation (Phase 5)
    print("\n[Phase 5] Testing Evaluator Agent...")
    eval_agent = EvaluatorAgent()
    
    # Load golden dataset
    with open("agentic/engine/evaluation/ground_truth.json", "r") as f:
        gt = json.load(f)
        
    # Mock current results for evaluation
    mock_results = [
        {"vendor_name": "Office Depot", "total_amount": "89.99", "currency": "USD"}
    ]
    
    eval_res, trace = await eval_agent.execute(mock_results, gt[:1])
    print(f"Evaluation Accuracy: {eval_res['average_accuracy']:.2%}")
    print(eval_agent.generate_report(eval_res))

if __name__ == "__main__":
    import json # Import locally for script
    asyncio.run(run_verification())
