"""
PDF extraction module for MediBrief.
"""

import os
import re
import json
import logging
import tempfile
from typing import Dict, List, Any, Optional, Tuple

import requests
import PyPDF2
from pdf2image import convert_from_path
import pytesseract
from pdfminer.high_level import extract_text
from PIL import Image

from utils.logger import get_logger

logger = get_logger()


class PDFExtractor:
    """
    Extract text, figures, and tables from PDF documents.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the PDF extractor.

        Args:
            config: Configuration dictionary containing PDF processing settings.
        """
        self.temp_storage_path = config["pdf_processing"]["temp_storage_path"]
        self.ocr_language = config["pdf_processing"]["ocr"]["language"]
        self.ocr_config = config["pdf_processing"]["ocr"]["config"]
        self.min_figure_size = config["pdf_processing"]["figure_extraction"]["min_figure_size"]
        self.caption_keywords = config["pdf_processing"]["figure_extraction"]["caption_keywords"]

        # Create temp directory if it doesn't exist
        if not os.path.exists(self.temp_storage_path):
            os.makedirs(self.temp_storage_path, exist_ok=True)

    def download_pdf(self, url: str, output_path: Optional[str] = None) -> str:
        """
        Download a PDF from a URL.

        Args:
            url: URL of the PDF to download.
            output_path: Path to save the PDF. If None, a temporary file will be created.

        Returns:
            Path to the downloaded PDF.

        Raises:
            Exception: If the download fails.
        """
        if output_path is None:
            output_path = os.path.join(self.temp_storage_path, f"{hash(url)}.pdf")

        try:
            logger.info(f"Downloading PDF from {url}")

            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()

            # Check if the response is a PDF
            content_type = response.headers.get("Content-Type", "")
            if "application/pdf" not in content_type:
                logger.warning(f"URL does not point to a PDF: {content_type}")

            # Save the PDF
            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info(f"PDF downloaded to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Error downloading PDF: {e}")
            raise

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """
        Extract text from a PDF document.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            Extracted text.
        """
        logger.info(f"Extracting text from {pdf_path}")

        try:
            # Use pdfminer for text extraction
            text = extract_text(pdf_path)

            # Clean up the text
            text = self._clean_text(text)

            logger.info(f"Extracted {len(text)} characters of text")
            return text

        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            return ""

    def _clean_text(self, text: str) -> str:
        """
        Clean up extracted text.

        Args:
            text: Raw extracted text.

        Returns:
            Cleaned text.
        """
        # Replace multiple newlines with a single newline
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Replace multiple spaces with a single space
        text = re.sub(r" {2,}", " ", text)

        # Remove page numbers
        text = re.sub(r"\n\s*\d+\s*\n", "\n", text)

        # Remove headers and footers (simplified approach)
        lines = text.split("\n")
        cleaned_lines = []

        for i, line in enumerate(lines):
            # Skip short lines at the top or bottom of pages
            if (i == 0 or i == len(lines) - 1) and len(line.strip()) < 50:
                continue

            # Skip lines that look like headers or footers
            if re.match(r"^[\d\s\-\.]+$", line.strip()):
                continue

            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def extract_abstract(self, text: str) -> str:
        """
        Extract the abstract from the paper text.

        Args:
            text: Full text of the paper.

        Returns:
            Abstract text.
        """
        # Look for the abstract section
        abstract_pattern = re.compile(
            r"(?:abstract|summary)(?:\s*\n\s*)(.*?)(?:\n\s*(?:introduction|background))",
            re.IGNORECASE | re.DOTALL
        )

        match = abstract_pattern.search(text)
        if match:
            abstract = match.group(1).strip()
            logger.info(f"Extracted abstract: {len(abstract)} characters")
            return abstract

        # If no abstract section found, try to extract the first paragraph
        paragraphs = text.split("\n\n")
        if paragraphs:
            first_para = paragraphs[0].strip()
            if 100 <= len(first_para) <= 1000:
                logger.info(f"Using first paragraph as abstract: {len(first_para)} characters")
                return first_para

        logger.warning("Could not extract abstract")
        return ""

    def extract_figures(self, pdf_path: str) -> List[Dict[str, Any]]:
        """
        Extract figures and their captions from a PDF.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            List of dictionaries containing figure data.
        """
        logger.info(f"Extracting figures from {pdf_path}")

        figures = []

        try:
            # Convert PDF to images
            images = convert_from_path(pdf_path, dpi=300)

            # Process each page
            for i, image in enumerate(images):
                page_figures = self._extract_figures_from_page(image, i + 1)
                figures.extend(page_figures)

            logger.info(f"Extracted {len(figures)} figures from PDF")
            return figures

        except Exception as e:
            logger.error(f"Error extracting figures: {e}")
            return []

    def _extract_figures_from_page(self, page_image: Image.Image, page_num: int) -> List[Dict[str, Any]]:
        """
        Extract figures from a single page image.

        Args:
            page_image: PIL Image of the page.
            page_num: Page number.

        Returns:
            List of dictionaries containing figure data.
        """
        figures = []

        # Save the page image temporarily
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            page_path = temp_file.name
            page_image.save(page_path)

        try:
            # Extract text from the page using OCR
            page_text = pytesseract.image_to_string(
                page_image,
                lang=self.ocr_language,
                config=self.ocr_config
            )

            # Look for figure captions
            caption_pattern = re.compile(
                r"((?:" + "|".join(self.caption_keywords) + r")\s*\d+[\.:]\s*[^\n]+)",
                re.IGNORECASE
            )

            captions = caption_pattern.findall(page_text)

            # If captions found, extract the figures
            for caption in captions:
                # Simple approach: save the entire page as the figure
                # In a production system, use image processing to extract just the figure
                figure_path = os.path.join(
                    self.temp_storage_path,
                    f"figure_p{page_num}_{hash(caption)}.png"
                )

                # Save a copy of the page as the figure
                page_image.save(figure_path)

                figures.append({
                    "page": page_num,
                    "caption": caption,
                    "path": figure_path,
                    "text": self._extract_text_from_figure(page_image)
                })

            # Clean up
            os.unlink(page_path)

            return figures

        except Exception as e:
            logger.error(f"Error processing page {page_num}: {e}")

            # Clean up
            if os.path.exists(page_path):
                os.unlink(page_path)

            return []

    def _extract_text_from_figure(self, figure_image: Image.Image) -> str:
        """
        Extract text from a figure using OCR.

        Args:
            figure_image: PIL Image of the figure.

        Returns:
            Extracted text.
        """
        try:
            text = pytesseract.image_to_string(
                figure_image,
                lang=self.ocr_language,
                config=self.ocr_config
            )

            return text.strip()

        except Exception as e:
            logger.error(f"Error extracting text from figure: {e}")
            return ""

    def extract_tables(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract tables from the paper text.

        Args:
            text: Full text of the paper.

        Returns:
            List of dictionaries containing table data.
        """
        logger.info("Extracting tables from text")

        tables = []

        # Look for table captions
        table_pattern = re.compile(
            r"(Table\s*\d+[\.:]\s*[^\n]+)",
            re.IGNORECASE
        )

        captions = table_pattern.findall(text)

        # For each caption, try to extract the table content
        for caption in captions:
            # Find the position of the caption
            caption_pos = text.find(caption)

            # Extract the text after the caption (simplified approach)
            table_text = text[caption_pos + len(caption):caption_pos + len(caption) + 1000]

            # Truncate at the next section or table
            next_section = re.search(r"\n\s*(?:[A-Z][a-z]+\s*)+\n", table_text)
            if next_section:
                table_text = table_text[:next_section.start()]

            next_table = re.search(r"Table\s*\d+[\.:]\s*", table_text)
            if next_table:
                table_text = table_text[:next_table.start()]

            tables.append({
                "caption": caption,
                "content": table_text.strip()
            })

        logger.info(f"Extracted {len(tables)} tables")
        return tables

    def process_pdf(self, pdf_path: str, output_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a PDF and extract all relevant information.

        Args:
            pdf_path: Path to the PDF file.
            output_dir: Directory to save extracted data. If None, use temp_storage_path.

        Returns:
            Dictionary containing all extracted data.
        """
        if output_dir is None:
            output_dir = self.temp_storage_path

        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        logger.info(f"Processing PDF: {pdf_path}")

        # Extract text
        text = self.extract_text_from_pdf(pdf_path)

        # Extract abstract
        abstract = self.extract_abstract(text)

        # Extract figures
        figures = self.extract_figures(pdf_path)

        # Extract tables
        tables = self.extract_tables(text)

        # Create result dictionary
        result = {
            "pdf_path": pdf_path,
            "text": text,
            "abstract": abstract,
            "figures": figures,
            "tables": tables
        }

        # Save result to JSON
        output_file = os.path.join(output_dir, f"{os.path.basename(pdf_path)}.json")
        with open(output_file, 'w') as f:
            # Convert non-serializable data
            serializable_result = result.copy()
            serializable_result["figures"] = [
                {k: str(v) if k == "image" else v for k, v in fig.items()}
                for fig in figures
            ]

            json.dump(serializable_result, f, indent=2)

        logger.info(f"PDF processing complete, results saved to {output_file}")
        return result