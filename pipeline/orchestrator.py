"""
Pipeline orchestrator for MediBrief.
"""

import os
import logging
import time
import json
import tempfile
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from pubmed.api import PubMedAPI
from pdf_processing.extractor import PDFExtractor
from ai_processing.vertex_ai import VertexAI
from image_analysis.vision_ai import VisionAI
from tts.speech_generator import SpeechGenerator
from video_generation.movie_creator import MovieCreator
from cloud_storage.storage_client import StorageClient
from youtube.uploader import YouTubeUploader

from utils.logger import get_logger

logger = get_logger()


class Orchestrator:
    """
    Orchestrator for the MediBrief pipeline.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the orchestrator.

        Args:
            config: Configuration dictionary.
        """
        self.config = config

        # Initialize components
        self.pubmed_api = PubMedAPI(config)
        self.pdf_extractor = PDFExtractor(config)
        self.vertex_ai = VertexAI(config)
        self.vision_ai = VisionAI(config)
        self.speech_generator = SpeechGenerator(config)
        self.movie_creator = MovieCreator(config)
        self.storage_client = StorageClient(config)
        self.youtube_uploader = YouTubeUploader(config)

        # Pipeline settings
        self.max_concurrent_papers = config["pipeline"]["max_concurrent_papers"]
        self.max_retries = config["pipeline"]["max_retries"]
        self.retry_delay = config["pipeline"]["retry_delay_seconds"]

        # Create output directories
        self.output_dir = "output"
        self.temp_dir = "temp"

        for directory in [self.output_dir, self.temp_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)

    def run(self) -> None:
        """
        Run the pipeline.
        """
        logger.info("Starting MediBrief pipeline")

        # Ensure Cloud Storage buckets exist
        self.storage_client.ensure_buckets_exist()

        # Process each specialty
        for specialty in self.config["pubmed"]["specialties"]:
            self._process_specialty(specialty)

        logger.info("MediBrief pipeline completed")

    def _process_specialty(self, specialty: str) -> None:
        """
        Process a medical specialty.

        Args:
            specialty: Medical specialty to process.
        """
        logger.info(f"Processing specialty: {specialty}")

        # Search for papers
        papers = self.pubmed_api.search_and_fetch_papers(
            specialty,
            days=self.config["pubmed"]["time_period_days"],
            max_results=self.config["pubmed"]["max_results_per_query"]
        )

        logger.info(f"Found {len(papers)} papers for {specialty}")

        # Save papers to JSON
        specialty_dir = os.path.join(self.output_dir, specialty)
        os.makedirs(specialty_dir, exist_ok=True)

        papers_file = os.path.join(specialty_dir, f"{specialty}_papers.json")
        self.pubmed_api.save_papers_to_json(papers, papers_file)

        # Process papers in parallel
        with ThreadPoolExecutor(max_workers=self.max_concurrent_papers) as executor:
            # Submit tasks
            futures = {
                executor.submit(self._process_paper, paper, specialty): paper
                for paper in papers
            }

            # Process results as they complete
            for future in as_completed(futures):
                paper = futures[future]
                try:
                    result = future.result()
                    logger.info(f"Completed processing paper: {paper.get('title', 'Unknown')}")
                except Exception as e:
                    logger.error(f"Error processing paper: {e}")

    def _process_paper(self, paper: Dict[str, Any], specialty: str) -> Dict[str, Any]:
        """
        Process a single paper.

        Args:
            paper: Paper data.
            specialty: Medical specialty.

        Returns:
            Dictionary containing processing results.
        """
        paper_id = paper.get("pmid", "unknown")
        title = paper.get("title", "Unknown Title")
        logger.info(f"Processing paper: {title} (ID: {paper_id})")

        # Create paper directory
        paper_dir = os.path.join(self.output_dir, specialty, paper_id)
        os.makedirs(paper_dir, exist_ok=True)

        # Save paper data
        paper_file = os.path.join(paper_dir, "paper_data.json")
        with open(paper_file, "w") as f:
            json.dump(paper, f, indent=2)

        try:
            # Step 1: Download and process PDF
            pdf_data = self._download_and_process_pdf(paper, paper_dir)

            # Step 2: Process with AI
            ai_data = self._process_with_ai(paper, pdf_data, paper_dir)

            # Step 3: Process figures
            figures_data = self._process_figures(pdf_data.get("figures", []), paper_dir)

            # Step 4: Generate narration
            audio_path = self._generate_narration(ai_data.get("narration_script", ""), paper_dir)

            # Step 5: Create video
            video_path = self._create_video(
                paper,
                ai_data.get("summary", ""),
                ai_data.get("key_takeaways", []),
                ai_data.get("clinical_relevance", ""),
                figures_data,
                audio_path,
                paper_dir
            )

            # Step 6: Upload to Cloud Storage
            video_url = self._upload_to_cloud_storage(video_path, paper_id, specialty)

            # Step 7: Upload to YouTube
            youtube_data = self._upload_to_youtube(
                video_path,
                paper,
                ai_data.get("key_takeaways", [])
            )

            # Save results
            result = {
                "paper_id": paper_id,
                "title": title,
                "specialty": specialty,
                "video_path": video_path,
                "video_url": video_url,
                "youtube_url": youtube_data.get("url", ""),
                "youtube_id": youtube_data.get("id", ""),
                "timestamp": datetime.now().isoformat()
            }

            result_file = os.path.join(paper_dir, "result.json")
            with open(result_file, "w") as f:
                json.dump(result, f, indent=2)

            return result

        except Exception as e:
            logger.error(f"Error processing paper {paper_id}: {e}")

            # Save error
            error_file = os.path.join(paper_dir, "error.json")
            with open(error_file, "w") as f:
                json.dump({
                    "paper_id": paper_id,
                    "title": title,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }, f, indent=2)

            raise

    def _download_and_process_pdf(self, paper: Dict[str, Any], paper_dir: str) -> Dict[str, Any]:
        """
        Download and process a PDF.

        Args:
            paper: Paper data.
            paper_dir: Directory to save results.

        Returns:
            Dictionary containing PDF processing results.
        """
        logger.info(f"Downloading and processing PDF for paper {paper.get('pmid', 'unknown')}")

        # Check if paper has a DOI
        doi = paper.get("doi", "")
        if not doi:
            # If no DOI, use the abstract only
            logger.warning(f"No DOI found for paper {paper.get('pmid', 'unknown')}, using abstract only")
            return {
                "text": paper.get("abstract", ""),
                "abstract": paper.get("abstract", ""),
                "figures": [],
                "tables": []
            }

        # Try to download the PDF
        try:
            # Construct a URL to the PDF (this is a simplified approach)
            # In a real system, you would need to handle different publisher URLs
            pdf_url = f"https://doi.org/{doi}"

            # Download the PDF
            pdf_path = os.path.join(paper_dir, f"{paper.get('pmid', 'unknown')}.pdf")

            # For demonstration purposes, we'll skip the actual download
            # since most papers require authentication
            # Instead, we'll create a dummy PDF with the abstract
            self._create_dummy_pdf(paper, pdf_path)

            # Process the PDF
            pdf_data = self.pdf_extractor.process_pdf(pdf_path, paper_dir)

            return pdf_data

        except Exception as e:
            logger.error(f"Error downloading/processing PDF: {e}")

            # Fall back to using the abstract only
            logger.warning(f"Using abstract only for paper {paper.get('pmid', 'unknown')}")
            return {
                "text": paper.get("abstract", ""),
                "abstract": paper.get("abstract", ""),
                "figures": [],
                "tables": []
            }

    def _create_dummy_pdf(self, paper: Dict[str, Any], pdf_path: str) -> None:
        """
        Create a dummy PDF with the paper abstract.
        This is used for demonstration purposes only.

        Args:
            paper: Paper data.
            pdf_path: Path to save the PDF.
        """
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph
            from reportlab.lib.units import inch

            doc = SimpleDocTemplate(pdf_path, pagesize=letter)
            styles = getSampleStyleSheet()

            # Create content
            content = []

            # Title
            title = Paragraph(paper.get("title", "Unknown Title"), styles["Title"])
            content.append(title)

            # Authors
            authors = Paragraph(
                "Authors: " + ", ".join(paper.get("authors", ["Unknown"])),
                styles["Normal"]
            )
            content.append(authors)

            # Journal and date
            journal = Paragraph(
                f"Journal: {paper.get('journal', 'Unknown')} - {paper.get('publication_date', 'Unknown')}",
                styles["Normal"]
            )
            content.append(journal)

            # Abstract
            abstract_title = Paragraph("Abstract", styles["Heading2"])
            content.append(abstract_title)

            abstract = Paragraph(paper.get("abstract", "No abstract available"), styles["Normal"])
            content.append(abstract)

            # Build the PDF
            doc.build(content)

            logger.info(f"Created dummy PDF at {pdf_path}")

        except Exception as e:
            logger.error(f"Error creating dummy PDF: {e}")

            # Create an empty file as fallback
            with open(pdf_path, "w") as f:
                f.write(f"Title: {paper.get('title', 'Unknown Title')}\n")
                f.write(f"Abstract: {paper.get('abstract', 'No abstract available')}\n")

    def _process_with_ai(
        self,
        paper: Dict[str, Any],
        pdf_data: Dict[str, Any],
        paper_dir: str
    ) -> Dict[str, Any]:
        """
        Process paper data with AI.

        Args:
            paper: Paper data.
            pdf_data: PDF processing results.
            paper_dir: Directory to save results.

        Returns:
            Dictionary containing AI processing results.
        """
        logger.info(f"Processing paper with AI: {paper.get('pmid', 'unknown')}")

        # Combine paper data with PDF data
        combined_data = {
            **paper,
            "text": pdf_data.get("text", paper.get("abstract", "")),
            "abstract": pdf_data.get("abstract", paper.get("abstract", ""))
        }

        # Process with Vertex AI
        ai_result = self.vertex_ai.process_paper(combined_data)

        # Save results
        ai_result_file = os.path.join(paper_dir, "ai_result.json")
        with open(ai_result_file, "w") as f:
            json.dump(ai_result, f, indent=2)

        return ai_result

    def _process_figures(
        self,
        figures: List[Dict[str, Any]],
        paper_dir: str
    ) -> List[Dict[str, Any]]:
        """
        Process figures with Vision AI.

        Args:
            figures: List of figures from PDF extraction.
            paper_dir: Directory to save results.

        Returns:
            List of processed figures.
        """
        logger.info(f"Processing {len(figures)} figures with Vision AI")

        if not figures:
            logger.warning("No figures to process")
            return []

        # Process figures with Vision AI
        processed_figures = self.vision_ai.process_figures(figures)

        # Save results
        figures_result_file = os.path.join(paper_dir, "figures_result.json")
        with open(figures_result_file, "w") as f:
            # Convert non-serializable data
            serializable_figures = []
            for figure in processed_figures:
                serializable_figure = {
                    key: (str(value) if key == "image" else value)
                    for key, value in figure.items()
                }
                serializable_figures.append(serializable_figure)

            json.dump(serializable_figures, f, indent=2)

        return processed_figures

    def _generate_narration(self, script: str, paper_dir: str) -> str:
        """
        Generate narration audio from script.

        Args:
            script: Narration script.
            paper_dir: Directory to save results.

        Returns:
            Path to the generated audio file.
        """
        logger.info("Generating narration audio")

        # Create audio directory
        audio_dir = os.path.join(paper_dir, "audio")
        os.makedirs(audio_dir, exist_ok=True)

        # Generate narration
        audio_path = self.speech_generator.generate_narration(
            script,
            audio_dir,
            "narration"
        )

        return audio_path

    def _create_video(
        self,
        paper: Dict[str, Any],
        summary: str,
        key_takeaways: List[str],
        clinical_relevance: str,
        figures: List[Dict[str, Any]],
        audio_path: str,
        paper_dir: str
    ) -> str:
        """
        Create a video from the processed data.

        Args:
            paper: Paper data.
            summary: Paper summary.
            key_takeaways: List of key takeaways.
            clinical_relevance: Clinical relevance text.
            figures: List of processed figures.
            audio_path: Path to the narration audio file.
            paper_dir: Directory to save results.

        Returns:
            Path to the created video.
        """
        logger.info("Creating video")

        # Create video directory
        video_dir = os.path.join(paper_dir, "video")
        os.makedirs(video_dir, exist_ok=True)

        # Create video
        video_path = os.path.join(video_dir, f"{paper.get('pmid', 'unknown')}.mp4")

        self.movie_creator.create_video(
            paper,
            summary,
            key_takeaways,
            clinical_relevance,
            figures,
            audio_path,
            video_path
        )

        return video_path

    def _upload_to_cloud_storage(
        self,
        video_path: str,
        paper_id: str,
        specialty: str
    ) -> str:
        """
        Upload a video to Cloud Storage.

        Args:
            video_path: Path to the video file.
            paper_id: Paper ID.
            specialty: Medical specialty.

        Returns:
            Public URL of the uploaded video.
        """
        logger.info(f"Uploading video to Cloud Storage: {video_path}")

        # Create a unique name for the video
        video_name = f"{specialty}/{paper_id}/{os.path.basename(video_path)}"

        # Upload the video
        video_url = self.storage_client.upload_video(video_path, video_name)

        return video_url

    def _upload_to_youtube(
        self,
        video_path: str,
        paper: Dict[str, Any],
        key_takeaways: List[str]
    ) -> Dict[str, Any]:
        """
        Upload a video to YouTube.

        Args:
            video_path: Path to the video file.
            paper: Paper data.
            key_takeaways: List of key takeaways.

        Returns:
            Dictionary containing upload results.
        """
        logger.info(f"Uploading video to YouTube: {video_path}")

        # Upload the video
        result = self.youtube_uploader.process_and_upload_video(
            video_path,
            paper,
            key_takeaways
        )

        return result