"""
Google Vision AI integration for MediBrief.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional, Tuple

from google.cloud import vision
from google.oauth2 import service_account
from google.api_core.exceptions import GoogleAPIError

from utils.logger import get_logger

logger = get_logger()


class VisionAI:
    """
    Google Vision AI client for image analysis.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the Vision AI client.

        Args:
            config: Configuration dictionary containing Vision AI settings.
        """
        self.project_id = config["api_keys"]["gcp_project_id"]
        self.max_results = config["image_analysis"]["vision_ai"]["max_results"]
        self.feature_types = config["image_analysis"]["vision_ai"]["feature_types"]

        # Figure selection settings
        self.max_figures = config["image_analysis"]["figure_selection"]["max_figures"]
        self.min_quality_score = config["image_analysis"]["figure_selection"]["min_quality_score"]

        # Initialize Vision AI client
        self._init_vision_ai(config)

    def _init_vision_ai(self, config: Dict[str, Any]) -> None:
        """
        Initialize the Vision AI client.

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

                self.client = vision.ImageAnnotatorClient(credentials=credentials)
            else:
                # Initialize with default credentials
                self.client = vision.ImageAnnotatorClient()

            logger.info("Initialized Vision AI client")

        except Exception as e:
            logger.error(f"Error initializing Vision AI: {e}")
            raise

    def analyze_image(self, image_path: str) -> Dict[str, Any]:
        """
        Analyze an image using Vision AI.

        Args:
            image_path: Path to the image file.

        Returns:
            Dictionary containing analysis results.
        """
        logger.info(f"Analyzing image: {image_path}")

        try:
            # Load the image
            with open(image_path, "rb") as image_file:
                content = image_file.read()

            image = vision.Image(content=content)

            # Create feature list
            features = []
            for feature_type in self.feature_types:
                features.append(
                    vision.Feature(
                        type_=getattr(vision.Feature.Type, feature_type),
                        max_results=self.max_results
                    )
                )

            # Perform image analysis
            response = self.client.annotate_image({
                "image": image,
                "features": features
            })

            # Process the response
            result = self._process_response(response)
            result["image_path"] = image_path

            logger.info(f"Image analysis complete for {image_path}")
            return result

        except Exception as e:
            logger.error(f"Error analyzing image: {e}")
            return {"image_path": image_path, "error": str(e)}

    def _process_response(self, response) -> Dict[str, Any]:
        """
        Process the Vision AI response.

        Args:
            response: Vision AI response.

        Returns:
            Dictionary containing processed results.
        """
        result = {}

        # Extract text annotations
        if response.text_annotations:
            result["text"] = response.text_annotations[0].description
            result["text_annotations"] = [
                {
                    "description": annotation.description,
                    "bounding_poly": [
                        {"x": vertex.x, "y": vertex.y}
                        for vertex in annotation.bounding_poly.vertices
                    ]
                }
                for annotation in response.text_annotations[1:]  # Skip the first one (full text)
            ]
        else:
            result["text"] = ""
            result["text_annotations"] = []

        # Extract labels
        if response.label_annotations:
            result["labels"] = [
                {
                    "description": label.description,
                    "score": label.score,
                    "topicality": label.topicality
                }
                for label in response.label_annotations
            ]
        else:
            result["labels"] = []

        # Extract objects
        if hasattr(response, "localized_object_annotations") and response.localized_object_annotations:
            result["objects"] = [
                {
                    "name": obj.name,
                    "score": obj.score,
                    "bounding_poly": [
                        {"x": vertex.x, "y": vertex.y}
                        for vertex in obj.bounding_poly.normalized_vertices
                    ]
                }
                for obj in response.localized_object_annotations
            ]
        else:
            result["objects"] = []

        # Extract image properties
        if response.image_properties_annotation:
            result["colors"] = [
                {
                    "color": {
                        "red": color.color.red,
                        "green": color.color.green,
                        "blue": color.color.blue
                    },
                    "score": color.score,
                    "pixel_fraction": color.pixel_fraction
                }
                for color in response.image_properties_annotation.dominant_colors.colors
            ]
        else:
            result["colors"] = []

        return result

    def detect_image_type(self, analysis_result: Dict[str, Any]) -> str:
        """
        Detect the type of medical image.

        Args:
            analysis_result: Vision AI analysis result.

        Returns:
            Image type (chart, graph, microscopy, table, other).
        """
        # Check for chart or graph
        chart_keywords = ["chart", "graph", "plot", "diagram", "axis", "bar", "pie", "line"]
        for label in analysis_result.get("labels", []):
            if any(keyword in label["description"].lower() for keyword in chart_keywords):
                return "chart"

        # Check for table
        table_keywords = ["table", "grid", "row", "column", "cell"]
        if any(keyword in analysis_result.get("text", "").lower() for keyword in table_keywords):
            return "table"

        # Check for microscopy
        microscopy_keywords = ["microscopy", "cell", "tissue", "histology", "pathology", "specimen"]
        for label in analysis_result.get("labels", []):
            if any(keyword in label["description"].lower() for keyword in microscopy_keywords):
                return "microscopy"

        # Default to other
        return "other"

    def calculate_importance_score(self, analysis_result: Dict[str, Any], figure_data: Dict[str, Any]) -> float:
        """
        Calculate an importance score for a figure.

        Args:
            analysis_result: Vision AI analysis result.
            figure_data: Figure data from PDF extraction.

        Returns:
            Importance score (0.0 to 1.0).
        """
        score = 0.0

        # Check if the figure has a caption
        if figure_data.get("caption"):
            score += 0.3

        # Check if the figure has text
        if analysis_result.get("text"):
            score += 0.2

        # Check if the figure is a chart, graph, or table
        image_type = self.detect_image_type(analysis_result)
        if image_type in ["chart", "table"]:
            score += 0.3
        elif image_type == "microscopy":
            score += 0.2

        # Check for relevant labels
        medical_keywords = [
            "medical", "clinical", "health", "patient", "treatment", "disease",
            "therapy", "diagnosis", "prognosis", "outcome", "survival", "mortality"
        ]

        for label in analysis_result.get("labels", []):
            if any(keyword in label["description"].lower() for keyword in medical_keywords):
                score += 0.1
                break

        # Ensure score is between 0 and 1
        return min(max(score, 0.0), 1.0)

    def select_top_figures(self, figures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Select the top figures based on importance score.

        Args:
            figures: List of figures with analysis results.

        Returns:
            List of selected figures.
        """
        logger.info(f"Selecting top {self.max_figures} figures from {len(figures)} candidates")

        # Filter figures by minimum quality score
        qualified_figures = [
            figure for figure in figures
            if figure.get("importance_score", 0) >= self.min_quality_score
        ]

        # Sort by importance score
        sorted_figures = sorted(
            qualified_figures,
            key=lambda x: x.get("importance_score", 0),
            reverse=True
        )

        # Select top figures
        selected_figures = sorted_figures[:self.max_figures]

        logger.info(f"Selected {len(selected_figures)} figures")
        return selected_figures

    def process_figures(self, figures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process a list of figures.

        Args:
            figures: List of figures from PDF extraction.

        Returns:
            List of processed figures with analysis results.
        """
        logger.info(f"Processing {len(figures)} figures")

        processed_figures = []

        for figure in figures:
            try:
                # Analyze the figure image
                image_path = figure.get("path")
                if not image_path or not os.path.exists(image_path):
                    logger.warning(f"Figure path not found: {image_path}")
                    continue

                # Analyze the image
                analysis_result = self.analyze_image(image_path)

                # Calculate importance score
                importance_score = self.calculate_importance_score(analysis_result, figure)

                # Detect image type
                image_type = self.detect_image_type(analysis_result)

                # Create processed figure
                processed_figure = {
                    **figure,
                    "analysis": analysis_result,
                    "importance_score": importance_score,
                    "image_type": image_type
                }

                processed_figures.append(processed_figure)

            except Exception as e:
                logger.error(f"Error processing figure: {e}")

        # Select top figures
        selected_figures = self.select_top_figures(processed_figures)

        return selected_figures