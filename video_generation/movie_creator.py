"""
Video generation module for MediBrief using MoviePy.
"""

import os
import logging
import tempfile
from typing import Dict, List, Any, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    AudioFileClip, ImageClip, TextClip, CompositeVideoClip,
    concatenate_videoclips, ColorClip, VideoFileClip
)
from moviepy.video.fx.fadein import fadein
from moviepy.video.fx.fadeout import fadeout

from utils.logger import get_logger

logger = get_logger()


class MovieCreator:
    """
    MoviePy-based video creator for MediBrief.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the movie creator.

        Args:
            config: Configuration dictionary containing video generation settings.
        """
        # Output settings
        self.resolution = self._parse_resolution(config["video_generation"]["output"]["resolution"])
        self.fps = config["video_generation"]["output"]["fps"]
        self.format = config["video_generation"]["output"]["format"]

        # Style settings
        self.background_color = config["video_generation"]["style"]["background_color"]
        self.text_color = config["video_generation"]["style"]["text_color"]
        self.highlight_color = config["video_generation"]["style"]["highlight_color"]
        self.font = config["video_generation"]["style"]["font"]
        self.title_font_size = config["video_generation"]["style"]["title_font_size"]
        self.body_font_size = config["video_generation"]["style"]["body_font_size"]

        # Timing settings
        self.intro_duration = config["video_generation"]["timing"]["intro_duration"]
        self.slide_duration = config["video_generation"]["timing"]["slide_duration"]
        self.transition_duration = config["video_generation"]["timing"]["transition_duration"]
        self.outro_duration = config["video_generation"]["timing"]["outro_duration"]

    def _parse_resolution(self, resolution: str) -> Tuple[int, int]:
        """
        Parse resolution string into width and height.

        Args:
            resolution: Resolution string (e.g., "1080p").

        Returns:
            Tuple of (width, height).
        """
        if resolution == "1080p":
            return (1920, 1080)
        elif resolution == "720p":
            return (1280, 720)
        elif resolution == "480p":
            return (854, 480)
        else:
            # Default to 1080p
            return (1920, 1080)

    def _create_title_slide(self, paper_data: Dict[str, Any]) -> ImageClip:
        """
        Create a title slide for the video.

        Args:
            paper_data: Dictionary containing paper data.

        Returns:
            ImageClip for the title slide.
        """
        logger.info("Creating title slide")

        # Create a blank image with the background color
        width, height = self.resolution
        image = Image.new("RGB", (width, height), self.background_color)
        draw = ImageDraw.Draw(image)

        # Load fonts
        try:
            title_font = ImageFont.truetype(self.font, self.title_font_size)
            body_font = ImageFont.truetype(self.font, self.body_font_size)
        except IOError:
            # Fall back to default font if the specified font is not available
            title_font = ImageFont.load_default()
            body_font = ImageFont.load_default()

        # Draw title
        title = paper_data.get("title", "Unknown Title")
        title_lines = self._wrap_text(title, width - 200, title_font)
        title_y = height // 4

        for line in title_lines:
            text_width = draw.textlength(line, font=title_font)
            draw.text(
                ((width - text_width) // 2, title_y),
                line,
                font=title_font,
                fill=self.text_color
            )
            title_y += title_font.size + 10

        # Draw authors
        authors = ", ".join(paper_data.get("authors", ["Unknown Authors"]))
        authors_lines = self._wrap_text(authors, width - 200, body_font)
        authors_y = title_y + 50

        for line in authors_lines:
            text_width = draw.textlength(line, font=body_font)
            draw.text(
                ((width - text_width) // 2, authors_y),
                line,
                font=body_font,
                fill=self.text_color
            )
            authors_y += body_font.size + 5

        # Draw journal and date
        journal = paper_data.get("journal", "Unknown Journal")
        date = paper_data.get("publication_date", "Unknown Date")
        journal_text = f"{journal} • {date}"
        journal_lines = self._wrap_text(journal_text, width - 200, body_font)
        journal_y = authors_y + 30

        for line in journal_lines:
            text_width = draw.textlength(line, font=body_font)
            draw.text(
                ((width - text_width) // 2, journal_y),
                line,
                font=body_font,
                fill=self.highlight_color
            )
            journal_y += body_font.size + 5

        # Save the image to a temporary file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            temp_path = temp_file.name
            image.save(temp_path)

        # Create an ImageClip from the temporary file
        clip = ImageClip(temp_path).set_duration(self.intro_duration)

        # Apply fade effects
        clip = fadein(clip, self.transition_duration)
        clip = fadeout(clip, self.transition_duration)

        return clip

    def _wrap_text(self, text: str, max_width: int, font: ImageFont.FreeTypeFont) -> List[str]:
        """
        Wrap text to fit within a maximum width.

        Args:
            text: Text to wrap.
            max_width: Maximum width in pixels.
            font: Font to use for measuring text width.

        Returns:
            List of wrapped text lines.
        """
        words = text.split()
        lines = []
        current_line = words[0]

        for word in words[1:]:
            # Check if adding this word would exceed the max width
            test_line = current_line + " " + word
            test_width = font.getlength(test_line)

            if test_width <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word

        # Add the last line
        lines.append(current_line)

        return lines

    def _create_summary_slide(self, summary: str) -> ImageClip:
        """
        Create a summary slide for the video.

        Args:
            summary: Paper summary text.

        Returns:
            ImageClip for the summary slide.
        """
        logger.info("Creating summary slide")

        # Create a blank image with the background color
        width, height = self.resolution
        image = Image.new("RGB", (width, height), self.background_color)
        draw = ImageDraw.Draw(image)

        # Load fonts
        try:
            title_font = ImageFont.truetype(self.font, self.title_font_size)
            body_font = ImageFont.truetype(self.font, int(self.body_font_size * 0.9))  # Slightly smaller for summary
        except IOError:
            # Fall back to default font if the specified font is not available
            title_font = ImageFont.load_default()
            body_font = ImageFont.load_default()

        # Draw title
        title = "Summary"
        title_width = draw.textlength(title, font=title_font)
        draw.text(
            ((width - title_width) // 2, 50),
            title,
            font=title_font,
            fill=self.highlight_color
        )

        # Draw summary text
        summary_lines = self._wrap_text(summary, width - 200, body_font)
        summary_y = 150

        for line in summary_lines:
            text_width = draw.textlength(line, font=body_font)
            draw.text(
                ((width - text_width) // 2, summary_y),
                line,
                font=body_font,
                fill=self.text_color
            )
            summary_y += body_font.size + 5

        # Save the image to a temporary file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            temp_path = temp_file.name
            image.save(temp_path)

        # Create an ImageClip from the temporary file
        clip = ImageClip(temp_path).set_duration(self.slide_duration)

        # Apply fade effects
        clip = fadein(clip, self.transition_duration)
        clip = fadeout(clip, self.transition_duration)

        return clip

    def _create_key_takeaways_slide(self, key_takeaways: List[str]) -> ImageClip:
        """
        Create a key takeaways slide for the video.

        Args:
            key_takeaways: List of key takeaways.

        Returns:
            ImageClip for the key takeaways slide.
        """
        logger.info("Creating key takeaways slide")

        # Create a blank image with the background color
        width, height = self.resolution
        image = Image.new("RGB", (width, height), self.background_color)
        draw = ImageDraw.Draw(image)

        # Load fonts
        try:
            title_font = ImageFont.truetype(self.font, self.title_font_size)
            body_font = ImageFont.truetype(self.font, self.body_font_size)
        except IOError:
            # Fall back to default font if the specified font is not available
            title_font = ImageFont.load_default()
            body_font = ImageFont.load_default()

        # Draw title
        title = "Key Takeaways"
        title_width = draw.textlength(title, font=title_font)
        draw.text(
            ((width - title_width) // 2, 50),
            title,
            font=title_font,
            fill=self.highlight_color
        )

        # Draw key takeaways
        takeaway_y = 150

        for i, takeaway in enumerate(key_takeaways):
            # Draw bullet point
            bullet = f"{i + 1}."
            bullet_width = draw.textlength(bullet, font=body_font)
            draw.text(
                (100, takeaway_y),
                bullet,
                font=body_font,
                fill=self.highlight_color
            )

            # Draw takeaway text
            takeaway_lines = self._wrap_text(takeaway, width - 250, body_font)
            for j, line in enumerate(takeaway_lines):
                draw.text(
                    (100 + bullet_width + 20, takeaway_y + j * (body_font.size + 5)),
                    line,
                    font=body_font,
                    fill=self.text_color
                )

            # Move to the next takeaway
            takeaway_y += (len(takeaway_lines) * (body_font.size + 5)) + 30

        # Save the image to a temporary file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            temp_path = temp_file.name
            image.save(temp_path)

        # Create an ImageClip from the temporary file
        clip = ImageClip(temp_path).set_duration(self.slide_duration)

        # Apply fade effects
        clip = fadein(clip, self.transition_duration)
        clip = fadeout(clip, self.transition_duration)

        return clip

    def _create_clinical_relevance_slide(self, clinical_relevance: str) -> ImageClip:
        """
        Create a clinical relevance slide for the video.

        Args:
            clinical_relevance: Clinical relevance text.

        Returns:
            ImageClip for the clinical relevance slide.
        """
        logger.info("Creating clinical relevance slide")

        # Create a blank image with the background color
        width, height = self.resolution
        image = Image.new("RGB", (width, height), self.background_color)
        draw = ImageDraw.Draw(image)

        # Load fonts
        try:
            title_font = ImageFont.truetype(self.font, self.title_font_size)
            body_font = ImageFont.truetype(self.font, self.body_font_size)
        except IOError:
            # Fall back to default font if the specified font is not available
            title_font = ImageFont.load_default()
            body_font = ImageFont.load_default()

        # Draw title
        title = "Clinical Relevance"
        title_width = draw.textlength(title, font=title_font)
        draw.text(
            ((width - title_width) // 2, 50),
            title,
            font=title_font,
            fill=self.highlight_color
        )

        # Draw clinical relevance text
        relevance_lines = self._wrap_text(clinical_relevance, width - 200, body_font)
        relevance_y = 150

        for line in relevance_lines:
            text_width = draw.textlength(line, font=body_font)
            draw.text(
                ((width - text_width) // 2, relevance_y),
                line,
                font=body_font,
                fill=self.text_color
            )
            relevance_y += body_font.size + 5

        # Save the image to a temporary file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            temp_path = temp_file.name
            image.save(temp_path)

        # Create an ImageClip from the temporary file
        clip = ImageClip(temp_path).set_duration(self.slide_duration)

        # Apply fade effects
        clip = fadein(clip, self.transition_duration)
        clip = fadeout(clip, self.transition_duration)

        return clip

    def _create_figure_slide(self, figure: Dict[str, Any]) -> ImageClip:
        """
        Create a slide for a figure.

        Args:
            figure: Dictionary containing figure data.

        Returns:
            ImageClip for the figure slide.
        """
        logger.info(f"Creating figure slide for {figure.get('path', 'Unknown')}")

        # Create a blank image with the background color
        width, height = self.resolution
        image = Image.new("RGB", (width, height), self.background_color)
        draw = ImageDraw.Draw(image)

        # Load fonts
        try:
            title_font = ImageFont.truetype(self.font, int(self.title_font_size * 0.8))  # Smaller for figure title
            body_font = ImageFont.truetype(self.font, int(self.body_font_size * 0.8))  # Smaller for figure caption
        except IOError:
            # Fall back to default font if the specified font is not available
            title_font = ImageFont.load_default()
            body_font = ImageFont.load_default()

        # Draw figure title
        caption = figure.get("caption", "")
        title_lines = self._wrap_text(caption, width - 200, title_font)
        title_y = 50

        for line in title_lines:
            text_width = draw.textlength(line, font=title_font)
            draw.text(
                ((width - text_width) // 2, title_y),
                line,
                font=title_font,
                fill=self.highlight_color
            )
            title_y += title_font.size + 5

        # Load and resize the figure image
        try:
            figure_path = figure.get("path")
            if not figure_path or not os.path.exists(figure_path):
                logger.warning(f"Figure path not found: {figure_path}")
                return None

            figure_image = Image.open(figure_path)

            # Calculate the maximum size for the figure
            max_figure_width = width - 200
            max_figure_height = height - 300  # Leave space for title and caption

            # Resize the figure while maintaining aspect ratio
            figure_width, figure_height = figure_image.size
            scale = min(max_figure_width / figure_width, max_figure_height / figure_height)
            new_width = int(figure_width * scale)
            new_height = int(figure_height * scale)

            figure_image = figure_image.resize((new_width, new_height), Image.LANCZOS)

            # Paste the figure onto the slide
            figure_x = (width - new_width) // 2
            figure_y = title_y + 20
            image.paste(figure_image, (figure_x, figure_y))

            # Draw figure caption
            caption_text = figure.get("text", "")
            if caption_text:
                caption_lines = self._wrap_text(caption_text, width - 200, body_font)
                caption_y = figure_y + new_height + 20

                for line in caption_lines:
                    text_width = draw.textlength(line, font=body_font)
                    draw.text(
                        ((width - text_width) // 2, caption_y),
                        line,
                        font=body_font,
                        fill=self.text_color
                    )
                    caption_y += body_font.size + 5

        except Exception as e:
            logger.error(f"Error creating figure slide: {e}")
            return None

        # Save the image to a temporary file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            temp_path = temp_file.name
            image.save(temp_path)

        # Create an ImageClip from the temporary file
        clip = ImageClip(temp_path).set_duration(self.slide_duration)

        # Apply fade effects
        clip = fadein(clip, self.transition_duration)
        clip = fadeout(clip, self.transition_duration)

        return clip

    def _create_outro_slide(self, paper_data: Dict[str, Any]) -> ImageClip:
        """
        Create an outro slide for the video.

        Args:
            paper_data: Dictionary containing paper data.

        Returns:
            ImageClip for the outro slide.
        """
        logger.info("Creating outro slide")

        # Create a blank image with the background color
        width, height = self.resolution
        image = Image.new("RGB", (width, height), self.background_color)
        draw = ImageDraw.Draw(image)

        # Load fonts
        try:
            title_font = ImageFont.truetype(self.font, self.title_font_size)
            body_font = ImageFont.truetype(self.font, self.body_font_size)
        except IOError:
            # Fall back to default font if the specified font is not available
            title_font = ImageFont.load_default()
            body_font = ImageFont.load_default()

        # Draw title
        title = "Thank You for Watching"
        title_width = draw.textlength(title, font=title_font)
        draw.text(
            ((width - title_width) // 2, height // 3),
            title,
            font=title_font,
            fill=self.highlight_color
        )

        # Draw paper reference
        reference_y = height // 2

        # Paper title
        title = paper_data.get("title", "Unknown Title")
        title_lines = self._wrap_text(title, width - 200, body_font)

        for line in title_lines:
            text_width = draw.textlength(line, font=body_font)
            draw.text(
                ((width - text_width) // 2, reference_y),
                line,
                font=body_font,
                fill=self.text_color
            )
            reference_y += body_font.size + 5

        # DOI
        doi = paper_data.get("doi", "")
        if doi:
            doi_text = f"DOI: {doi}"
            doi_width = draw.textlength(doi_text, font=body_font)
            draw.text(
                ((width - doi_width) // 2, reference_y + 20),
                doi_text,
                font=body_font,
                fill=self.text_color
            )

        # Save the image to a temporary file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            temp_path = temp_file.name
            image.save(temp_path)

        # Create an ImageClip from the temporary file
        clip = ImageClip(temp_path).set_duration(self.outro_duration)

        # Apply fade effects
        clip = fadein(clip, self.transition_duration)
        clip = fadeout(clip, self.transition_duration)

        return clip

    def create_video(
        self,
        paper_data: Dict[str, Any],
        summary: str,
        key_takeaways: List[str],
        clinical_relevance: str,
        figures: List[Dict[str, Any]],
        audio_path: str,
        output_path: str
    ) -> str:
        """
        Create a video from the processed paper data.

        Args:
            paper_data: Dictionary containing paper data.
            summary: Paper summary text.
            key_takeaways: List of key takeaways.
            clinical_relevance: Clinical relevance text.
            figures: List of processed figures.
            audio_path: Path to the narration audio file.
            output_path: Path to save the output video.

        Returns:
            Path to the created video.
        """
        logger.info("Creating video")

        # Create slides
        slides = []

        # Title slide
        title_slide = self._create_title_slide(paper_data)
        if title_slide:
            slides.append(title_slide)

        # Summary slide
        summary_slide = self._create_summary_slide(summary)
        if summary_slide:
            slides.append(summary_slide)

        # Key takeaways slide
        takeaways_slide = self._create_key_takeaways_slide(key_takeaways)
        if takeaways_slide:
            slides.append(takeaways_slide)

        # Figure slides
        for figure in figures:
            figure_slide = self._create_figure_slide(figure)
            if figure_slide:
                slides.append(figure_slide)

        # Clinical relevance slide
        relevance_slide = self._create_clinical_relevance_slide(clinical_relevance)
        if relevance_slide:
            slides.append(relevance_slide)

        # Outro slide
        outro_slide = self._create_outro_slide(paper_data)
        if outro_slide:
            slides.append(outro_slide)

        # Concatenate slides
        video = concatenate_videoclips(slides, method="compose")

        # Add audio
        try:
            audio = AudioFileClip(audio_path)

            # If audio is longer than video, extend video duration
            if audio.duration > video.duration:
                # Create a blank clip for the remaining audio
                blank_duration = audio.duration - video.duration
                blank_clip = ColorClip(
                    size=self.resolution,
                    color=self.background_color,
                    duration=blank_duration
                )

                # Add fade effects
                blank_clip = fadein(blank_clip, self.transition_duration)
                blank_clip = fadeout(blank_clip, self.transition_duration)

                # Concatenate with the main video
                video = concatenate_videoclips([video, blank_clip], method="compose")

            # Set audio
            video = video.set_audio(audio)

        except Exception as e:
            logger.error(f"Error adding audio to video: {e}")

        # Write the video file
        try:
            video.write_videofile(
                output_path,
                fps=self.fps,
                codec="libx264",
                audio_codec="aac",
                threads=4,
                preset="medium"
            )

            logger.info(f"Video created and saved to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Error writing video file: {e}")
            raise

        finally:
            # Clean up temporary files
            for slide in slides:
                try:
                    os.remove(slide.filename)
                except:
                    pass