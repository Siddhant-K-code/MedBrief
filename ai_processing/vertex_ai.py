"""
Google Vertex AI integration for MediBrief.
"""

import json
import logging
import time
from typing import Dict, List, Any, Optional, Tuple

from google.cloud import aiplatform
from google.oauth2 import service_account
from google.api_core.exceptions import GoogleAPIError

from utils.logger import get_logger

logger = get_logger()


class VertexAI:
    """
    Google Vertex AI client for text processing.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the Vertex AI client.

        Args:
            config: Configuration dictionary containing Vertex AI settings.
        """
        self.project_id = config["api_keys"]["gcp_project_id"]
        self.location = config["ai_processing"]["vertex_ai"]["location"]
        self.model_name = config["ai_processing"]["vertex_ai"]["model_name"]

        # Summarization settings
        self.max_length = config["ai_processing"]["summarization"]["max_length"]
        self.min_length = config["ai_processing"]["summarization"]["min_length"]
        self.temperature = config["ai_processing"]["summarization"]["temperature"]
        self.top_p = config["ai_processing"]["summarization"]["top_p"]

        # Key takeaways settings
        self.key_takeaways_count = config["ai_processing"]["key_takeaways"]["count"]
        self.key_takeaways_max_length = config["ai_processing"]["key_takeaways"]["max_length_each"]

        # Initialize Vertex AI
        self._init_vertex_ai(config)

        # Maximum retries for API calls
        self.max_retries = 3
        self.retry_delay = 2  # seconds

    def _init_vertex_ai(self, config: Dict[str, Any]) -> None:
        """
        Initialize the Vertex AI client.

        Args:
            config: Configuration dictionary.
        """
        try:
            # Check if service account key file is provided
            service_account_key = config["api_keys"].get("gcp_service_account_key")

            if service_account_key:
                # Initialize with service account
                credentials = service_account.Credentials.from_service_account_file(
                    service_account_key
                )

                aiplatform.init(
                    project=self.project_id,
                    location=self.location,
                    credentials=credentials
                )
            else:
                # Initialize with default credentials
                aiplatform.init(
                    project=self.project_id,
                    location=self.location
                )

            logger.info(f"Initialized Vertex AI client for project {self.project_id}")

        except Exception as e:
            logger.error(f"Error initializing Vertex AI: {e}")
            raise

    def _retry_api_call(self, func, *args, **kwargs):
        """
        Retry an API call with exponential backoff.

        Args:
            func: Function to call.
            *args: Arguments to pass to the function.
            **kwargs: Keyword arguments to pass to the function.

        Returns:
            Result of the function call.

        Raises:
            Exception: If all retries fail.
        """
        retries = 0
        last_exception = None

        while retries < self.max_retries:
            try:
                return func(*args, **kwargs)
            except GoogleAPIError as e:
                last_exception = e
                retries += 1

                if retries < self.max_retries:
                    sleep_time = self.retry_delay * (2 ** (retries - 1))  # Exponential backoff
                    logger.warning(f"API call failed, retrying in {sleep_time} seconds: {e}")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"API call failed after {self.max_retries} retries: {e}")

        raise last_exception

    def generate_text(self, prompt: str, max_output_tokens: int = 1024) -> str:
        """
        Generate text using Vertex AI.

        Args:
            prompt: Prompt to generate text from.
            max_output_tokens: Maximum number of tokens to generate.

        Returns:
            Generated text.
        """
        logger.info(f"Generating text with prompt: {prompt[:100]}...")

        try:
            # Get the model
            model = aiplatform.GenerativeModel(self.model_name)

            # Set generation parameters
            generation_config = {
                "max_output_tokens": max_output_tokens,
                "temperature": self.temperature,
                "top_p": self.top_p
            }

            # Generate content
            response = self._retry_api_call(
                model.generate_content,
                prompt,
                generation_config=generation_config
            )

            # Extract text from response
            text = response.text

            logger.info(f"Generated {len(text)} characters of text")
            return text

        except Exception as e:
            logger.error(f"Error generating text: {e}")
            return ""

    def summarize_paper(self, paper_data: Dict[str, Any]) -> str:
        """
        Summarize a research paper.

        Args:
            paper_data: Dictionary containing paper data.

        Returns:
            Summary text.
        """
        logger.info(f"Summarizing paper: {paper_data.get('title', 'Unknown')}")

        # Construct the prompt
        prompt = f"""
        Summarize the following medical research paper in {self.min_length}-{self.max_length} words.
        Focus on the main findings, methodology, and clinical implications.
        Use clear, concise language suitable for medical professionals.

        Title: {paper_data.get('title', 'Unknown')}
        Authors: {', '.join(paper_data.get('authors', ['Unknown']))}
        Journal: {paper_data.get('journal', 'Unknown')}
        Publication Date: {paper_data.get('publication_date', 'Unknown')}

        Abstract:
        {paper_data.get('abstract', 'No abstract available')}

        Full Text:
        {paper_data.get('text', '')[:10000]}  # Limit text to avoid token limits
        """

        # Generate summary
        summary = self.generate_text(
            prompt,
            max_output_tokens=self.max_length * 2  # Approximate token count
        )

        return summary

    def generate_narration_script(self, summary: str, paper_data: Dict[str, Any]) -> str:
        """
        Generate a narration script from a paper summary.

        Args:
            summary: Paper summary.
            paper_data: Dictionary containing paper data.

        Returns:
            Narration script.
        """
        logger.info("Generating narration script")

        # Construct the prompt
        prompt = f"""
        Create a natural-sounding narration script for a video about this medical research paper.
        The script should be engaging, clear, and optimized for text-to-speech.
        Include appropriate pauses and emphasis where needed.

        Title: {paper_data.get('title', 'Unknown')}
        Authors: {', '.join(paper_data.get('authors', ['Unknown']))}
        Journal: {paper_data.get('journal', 'Unknown')}
        Publication Date: {paper_data.get('publication_date', 'Unknown')}

        Paper Summary:
        {summary}

        Format the script with clear sections:
        1. Introduction (paper title, authors, journal)
        2. Main findings
        3. Methodology
        4. Clinical implications
        5. Conclusion

        Use natural transitions between sections and avoid complex sentence structures.
        """

        # Generate narration script
        script = self.generate_text(prompt, max_output_tokens=2048)

        return script

    def extract_key_takeaways(self, summary: str, paper_data: Dict[str, Any]) -> List[str]:
        """
        Extract key takeaways from a paper summary.

        Args:
            summary: Paper summary.
            paper_data: Dictionary containing paper data.

        Returns:
            List of key takeaways.
        """
        logger.info("Extracting key takeaways")

        # Construct the prompt
        prompt = f"""
        Extract exactly {self.key_takeaways_count} key takeaways from this medical research paper.
        Each takeaway should be a single, concise sentence (maximum {self.key_takeaways_max_length} characters).
        Focus on the most important findings and clinical implications.

        Title: {paper_data.get('title', 'Unknown')}

        Paper Summary:
        {summary}

        Format your response as a numbered list with exactly {self.key_takeaways_count} items.
        """

        # Generate key takeaways
        response = self.generate_text(prompt, max_output_tokens=1024)

        # Parse the response to extract the numbered list
        takeaways = []
        for line in response.split('\n'):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith('- ')):
                # Remove the number/bullet and any leading/trailing whitespace
                takeaway = line.lstrip('0123456789.- ').strip()
                if takeaway:
                    takeaways.append(takeaway)

        # Ensure we have the exact number of takeaways
        if len(takeaways) > self.key_takeaways_count:
            takeaways = takeaways[:self.key_takeaways_count]

        # If we don't have enough takeaways, generate more
        if len(takeaways) < self.key_takeaways_count:
            logger.warning(f"Only extracted {len(takeaways)} takeaways, expected {self.key_takeaways_count}")

        return takeaways

    def identify_clinical_relevance(self, summary: str, paper_data: Dict[str, Any]) -> str:
        """
        Identify clinical relevance for practicing physicians.

        Args:
            summary: Paper summary.
            paper_data: Dictionary containing paper data.

        Returns:
            Clinical relevance text.
        """
        logger.info("Identifying clinical relevance")

        # Construct the prompt
        prompt = f"""
        Identify the clinical relevance of this medical research paper for practicing physicians.
        Focus on how the findings might impact clinical practice, patient care, or treatment decisions.
        Be specific about which medical specialties would benefit most from this research.

        Title: {paper_data.get('title', 'Unknown')}

        Paper Summary:
        {summary}

        Write a concise paragraph (150-250 words) about the clinical relevance.
        """

        # Generate clinical relevance
        clinical_relevance = self.generate_text(prompt, max_output_tokens=512)

        return clinical_relevance

    def process_paper(self, paper_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a paper with all AI tasks.

        Args:
            paper_data: Dictionary containing paper data.

        Returns:
            Dictionary containing processed data.
        """
        logger.info(f"Processing paper: {paper_data.get('title', 'Unknown')}")

        # Generate summary
        summary = self.summarize_paper(paper_data)

        # Generate narration script
        narration_script = self.generate_narration_script(summary, paper_data)

        # Extract key takeaways
        key_takeaways = self.extract_key_takeaways(summary, paper_data)

        # Identify clinical relevance
        clinical_relevance = self.identify_clinical_relevance(summary, paper_data)

        # Create result dictionary
        result = {
            "paper_data": paper_data,
            "summary": summary,
            "narration_script": narration_script,
            "key_takeaways": key_takeaways,
            "clinical_relevance": clinical_relevance
        }

        return result