"""
Evaluator Agent - Specializes in regression testing and accuracy metrics.
"""

import json
from typing import Any, Dict, List
from agentic_core.agents.base_agent import BaseAgent

class EvaluatorAgent(BaseAgent):
    agent_name = "evaluator_agent"
    agent_version = "0.1.0"

    async def run(self, results: List[Dict[str, Any]], ground_truth: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compare extraction results against ground truth.
        """
        self.log_step("Starting evaluation run")
        
        scores = []
        for res, gt in zip(results, ground_truth):
            accuracy = self._calculate_accuracy(res, gt["ground_truth"])
            scores.append({
                "filename": gt["filename"],
                "accuracy": accuracy
            })
            
        avg_accuracy = sum(s["accuracy"] for s in scores) / len(scores) if scores else 0
        
        self.log_step(f"Evaluation complete. Average accuracy: {avg_accuracy:.2%}")
        
        return {
            "average_accuracy": avg_accuracy,
            "detailed_scores": scores
        }

    def _calculate_accuracy(self, result: Dict[str, Any], ground_truth: Dict[str, Any]) -> float:
        """Simple accuracy calculation."""
        matches = 0
        total = len(ground_truth)
        
        for key, expected in ground_truth.items():
            if str(result.get(key)) == str(expected):
                matches += 1
                
        return matches / total if total > 0 else 0
        
    def generate_report(self, eval_result: Dict[str, Any]) -> str:
        """Generate a human-readable report."""
        report = f"# Agentic Evaluation Report\n\n"
        report += f"**Overall Accuracy**: {eval_result['average_accuracy']:.2%}\n\n"
        report += "## Detailed Results\n"
        for score in eval_result['detailed_scores']:
            report += f"- {score['filename']}: {score['accuracy']:.2%}\n"
        return report
