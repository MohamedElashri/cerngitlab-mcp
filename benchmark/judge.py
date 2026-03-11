"""
AI Judge module for scoring benchmark responses.

Uses the same LiteLLM API to evaluate model responses against reference answers.
Scores from 1-5 based on accuracy, completeness, and correctness.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Optional

import httpx

from .config import BenchmarkConfig

logger = logging.getLogger(__name__)


@dataclass
class JudgeResult:
    """Result from AI judge evaluation."""

    question_id: str
    score: int  # 1-5
    reasoning: str
    facts_correct: list[str]
    facts_incorrect: list[str]
    facts_missing: list[str]
    hallucinations: list[str]
    evaluation_time: float  # seconds
    confidence: float  # 0.0-1.0


class AIJudge:
    """AI Judge for evaluating benchmark responses."""

    SYSTEM_PROMPT = """You are an expert evaluator for CERN GitLab benchmark responses.
Your task is to score model responses from 1-5 based on accuracy compared to reference answers.

SCORING CRITERIA:
- 5/5: All facts correct, properly sourced, complete answer
- 4/5: Minor details incorrect but core facts accurate
- 3/5: Major facts correct but missing key details
- 2/5: Some correct information but significant errors
- 1/5: Mostly incorrect or hallucinated information
- 0/5: No answer or completely wrong

EVALUATION GUIDELINES:
1. Focus on factual accuracy - project IDs, paths, versions, names must be exact
2. Check for hallucinations - information not present in reference
3. Consider completeness - did it answer all parts of the question?
4. Be strict on technical details (IDs, versions, paths)
5. Be lenient on wording differences if meaning is the same

For each evaluation, provide:
1. Score (integer 0-5)
2. Reasoning (brief explanation)
3. List of correct facts mentioned
4. List of incorrect facts (with correction)
5. List of missing required facts
6. List of hallucinations (invented information)
7. Confidence level (0.0-1.0)"""

    EVALUATION_TEMPLATE = """QUESTION: {question}

REFERENCE ANSWER:
{reference_answer}

KEY FACTS TO CHECK:
{key_facts}

MODEL RESPONSE:
{model_response}

Provide your evaluation in JSON format with this exact structure:
{{
    "score": <integer 0-5>,
    "reasoning": "<brief explanation>",
    "facts_correct": ["fact1", "fact2", ...],
    "facts_incorrect": [{{"stated": "wrong fact", "correct": "right fact"}}],
    "facts_missing": ["missing fact1", "missing fact2"],
    "hallucinations": ["invented fact1", "invented fact2"],
    "confidence": <float 0.0-1.0>
}}"""

    def __init__(self, config: BenchmarkConfig):
        """Initialize AI Judge.

        Args:
            config: Benchmark configuration with API credentials.
        """
        self.config = config
        self.session = httpx.AsyncClient(
            timeout=config.llm_timeout,
            headers={
                "Authorization": f"Bearer {config.litellm_api_key}",
                "Content-Type": "application/json",
            },
        )

    async def close(self) -> None:
        """Close the HTTP session."""
        await self.session.aclose()

    async def evaluate(
        self,
        question_id: str,
        question: str,
        reference_answer: dict,
        model_response: str,
    ) -> JudgeResult:
        """Evaluate a model response against reference answer.

        Args:
            question_id: Unique identifier for the question.
            question: The original question text.
            reference_answer: Reference answer with facts and scoring criteria.
            model_response: The model's response to evaluate.

        Returns:
            JudgeResult with score and detailed evaluation.
        """
        start_time = time.time()

        # Build the evaluation prompt
        key_facts = self._format_key_facts(reference_answer)
        prompt = self.EVALUATION_TEMPLATE.format(
            question=question,
            reference_answer=reference_answer.get("full_answer", ""),
            key_facts=key_facts,
            model_response=model_response,
        )

        # Call the LLM for evaluation
        evaluation_json = await self._call_llm(prompt)

        # Parse the result
        evaluation_time = time.time() - start_time
        result = self._parse_evaluation(
            question_id, evaluation_json, evaluation_time
        )

        logger.info(
            f"Judge evaluation for {question_id}: score={result.score}/5, "
            f"time={evaluation_time:.2f}s, confidence={result.confidence:.2f}"
        )

        return result

    def _format_key_facts(self, reference_answer: dict) -> str:
        """Format key facts from reference answer for the judge."""
        facts = reference_answer.get("facts", {})
        if not facts:
            return "No structured facts provided."

        lines = []
        for key, value in facts.items():
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            lines.append(f"- {key}: {value}")
        return "\n".join(lines)

    async def _call_llm(self, prompt: str) -> dict:
        """Call LiteLLM API for evaluation.

        Args:
            prompt: The evaluation prompt.

        Returns:
            Parsed JSON response from the model.

        Raises:
            httpx.HTTPError: If API call fails.
            ValueError: If response cannot be parsed.
        """
        payload = {
            "model": self.config.litellm_model,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,  # Low temperature for consistent evaluation
            "max_tokens": 2000,
        }

        for attempt in range(self.config.max_retries):
            try:
                response = await self.session.post(
                    self.config.chat_completions_endpoint, json=payload
                )
                response.raise_for_status()
                data = response.json()

                content = data["choices"][0]["message"]["content"]

                # Parse JSON from response
                # Handle potential markdown code blocks
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

                return json.loads(content)

            except httpx.TimeoutException as e:
                logger.warning(
                    f"Judge API timeout (attempt {attempt + 1}/"
                    f"{self.config.max_retries}): {e}"
                )
                if attempt == self.config.max_retries - 1:
                    raise
                await asyncio.sleep(self.config.retry_delay)

            except httpx.HTTPError as e:
                logger.error(f"Judge API error: {e}")
                raise

        raise ValueError("Failed to call LLM after all retries")

    def _parse_evaluation(
        self, question_id: str, evaluation: dict, evaluation_time: float
    ) -> JudgeResult:
        """Parse evaluation JSON into JudgeResult.

        Args:
            question_id: Question identifier.
            evaluation: Raw evaluation dictionary from LLM.
            evaluation_time: Time taken for evaluation.

        Returns:
            Parsed JudgeResult.
        """
        try:
            score = int(evaluation.get("score", 0))
            score = max(0, min(5, score))  # Clamp to 0-5

            reasoning = str(evaluation.get("reasoning", "No reasoning provided."))

            facts_correct = evaluation.get("facts_correct", [])
            facts_incorrect = evaluation.get("facts_incorrect", [])
            facts_missing = evaluation.get("facts_missing", [])
            hallucinations = evaluation.get("hallucinations", [])

            confidence = float(evaluation.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))  # Clamp to 0-1

        except (ValueError, TypeError) as e:
            logger.error(f"Error parsing evaluation for {question_id}: {e}")
            score = 0
            reasoning = f"Error parsing evaluation: {e}"
            facts_correct = []
            facts_incorrect = []
            facts_missing = []
            hallucinations = []
            confidence = 0.0

        return JudgeResult(
            question_id=question_id,
            score=score,
            reasoning=reasoning,
            facts_correct=facts_correct,
            facts_incorrect=facts_incorrect,
            facts_missing=facts_missing,
            hallucinations=hallucinations,
            evaluation_time=evaluation_time,
            confidence=confidence,
        )
