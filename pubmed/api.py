"""
PubMed API integration for MediBrief.
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

import requests
from requests.exceptions import RequestException

from utils.logger import get_logger

# Constants
PUBMED_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
PUBMED_SEARCH_URL = f"{PUBMED_BASE_URL}/esearch.fcgi"
PUBMED_FETCH_URL = f"{PUBMED_BASE_URL}/efetch.fcgi"
PUBMED_SUMMARY_URL = f"{PUBMED_BASE_URL}/esummary.fcgi"

logger = get_logger()


class PubMedAPI:
    """
    PubMed API client for fetching medical research papers.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the PubMed API client.

        Args:
            config: Configuration dictionary containing PubMed API settings.
        """
        self.api_key = config["api_keys"].get("pubmed", "")
        self.max_results = config["pubmed"]["max_results_per_query"]
        self.rate_limit = config["pubmed"]["rate_limit"]
        self.default_fields = config["pubmed"]["default_fields"]
        self.last_request_time = 0

    def _respect_rate_limit(self) -> None:
        """
        Ensure that requests are made within the rate limit.
        """
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time

        # If we've made a request recently, wait until we're within the rate limit
        if time_since_last_request < (1.0 / self.rate_limit):
            sleep_time = (1.0 / self.rate_limit) - time_since_last_request
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def _make_request(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make a request to the PubMed API with rate limiting.

        Args:
            url: API endpoint URL.
            params: Query parameters.

        Returns:
            JSON response as a dictionary.

        Raises:
            RequestException: If the request fails.
        """
        # Add API key if available
        if self.api_key:
            params["api_key"] = self.api_key

        # Respect rate limit
        self._respect_rate_limit()

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            # Check if response is JSON
            if "json" in response.headers.get("Content-Type", ""):
                return response.json()
            else:
                # Parse XML response
                return {"raw_content": response.text}

        except RequestException as e:
            logger.error(f"PubMed API request failed: {e}")
            raise

    def search_papers(
        self,
        specialty: str,
        days: int = 7,
        max_results: Optional[int] = None
    ) -> List[str]:
        """
        Search for papers in a specific medical specialty.

        Args:
            specialty: Medical specialty to search for.
            days: Number of days to look back for papers.
            max_results: Maximum number of results to return.

        Returns:
            List of PubMed IDs (PMIDs) for matching papers.
        """
        if max_results is None:
            max_results = self.max_results

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # Format dates for PubMed API
        date_range = f"{start_date.strftime('%Y/%m/%d')}:{end_date.strftime('%Y/%m/%d')}[pdat]"

        # Construct search query
        query = f"{specialty}[MeSH Terms] AND {date_range} AND hasabstract[text]"

        logger.info(f"Searching PubMed for: {query}")

        # Set up parameters
        params = {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": max_results,
            "sort": "relevance"
        }

        try:
            response = self._make_request(PUBMED_SEARCH_URL, params)

            if "esearchresult" in response:
                pmids = response["esearchresult"].get("idlist", [])
                count = response["esearchresult"].get("count", "0")

                logger.info(f"Found {count} papers, retrieving {len(pmids)} results")
                return pmids
            else:
                logger.warning("Unexpected response format from PubMed search")
                return []

        except Exception as e:
            logger.error(f"Error searching PubMed: {e}")
            return []

    def fetch_paper_details(self, pmid: str) -> Dict[str, Any]:
        """
        Fetch detailed information for a specific paper.

        Args:
            pmid: PubMed ID of the paper.

        Returns:
            Dictionary containing paper details.
        """
        logger.info(f"Fetching details for paper PMID: {pmid}")

        params = {
            "db": "pubmed",
            "id": pmid,
            "retmode": "json"
        }

        try:
            response = self._make_request(PUBMED_SUMMARY_URL, params)

            if "result" in response and pmid in response["result"]:
                paper_data = response["result"][pmid]

                # Extract and format the data
                paper_details = {
                    "pmid": pmid,
                    "title": paper_data.get("title", ""),
                    "abstract": self._fetch_abstract(pmid),
                    "authors": [author.get("name", "") for author in paper_data.get("authors", [])],
                    "journal": paper_data.get("fulljournalname", ""),
                    "publication_date": paper_data.get("pubdate", ""),
                    "doi": paper_data.get("elocationid", "").replace("doi: ", "") if "elocationid" in paper_data else "",
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                }

                return paper_details
            else:
                logger.warning(f"Paper details not found for PMID: {pmid}")
                return {"pmid": pmid, "error": "Details not found"}

        except Exception as e:
            logger.error(f"Error fetching paper details: {e}")
            return {"pmid": pmid, "error": str(e)}

    def _fetch_abstract(self, pmid: str) -> str:
        """
        Fetch the abstract for a specific paper.

        Args:
            pmid: PubMed ID of the paper.

        Returns:
            Abstract text.
        """
        params = {
            "db": "pubmed",
            "id": pmid,
            "retmode": "xml",
            "rettype": "abstract"
        }

        try:
            response = self._make_request(PUBMED_FETCH_URL, params)

            # For XML responses, we get raw content
            if "raw_content" in response:
                # Simple extraction of abstract from XML
                # In a production system, use a proper XML parser
                xml_content = response["raw_content"]

                # Extract abstract using simple string operations
                # This is a simplified approach - a real implementation would use XML parsing
                if "<AbstractText>" in xml_content and "</AbstractText>" in xml_content:
                    start = xml_content.find("<AbstractText>") + len("<AbstractText>")
                    end = xml_content.find("</AbstractText>")
                    abstract = xml_content[start:end]

                    # Clean up XML entities
                    abstract = abstract.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

                    return abstract

            return "Abstract not available"

        except Exception as e:
            logger.error(f"Error fetching abstract: {e}")
            return "Error retrieving abstract"

    def search_and_fetch_papers(
        self,
        specialty: str,
        days: int = 7,
        max_results: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for papers and fetch their details in one operation.

        Args:
            specialty: Medical specialty to search for.
            days: Number of days to look back for papers.
            max_results: Maximum number of results to return.

        Returns:
            List of dictionaries containing paper details.
        """
        # Search for papers
        pmids = self.search_papers(specialty, days, max_results)

        # Fetch details for each paper
        papers = []
        for pmid in pmids:
            try:
                paper_details = self.fetch_paper_details(pmid)
                papers.append(paper_details)

                # Add a small delay between requests
                time.sleep(0.5)

            except Exception as e:
                logger.error(f"Error processing paper {pmid}: {e}")

        return papers

    def save_papers_to_json(self, papers: List[Dict[str, Any]], output_file: str) -> None:
        """
        Save paper details to a JSON file.

        Args:
            papers: List of paper details.
            output_file: Path to output JSON file.
        """
        try:
            with open(output_file, 'w') as f:
                json.dump(papers, f, indent=2)

            logger.info(f"Saved {len(papers)} papers to {output_file}")

        except Exception as e:
            logger.error(f"Error saving papers to JSON: {e}")
            raise