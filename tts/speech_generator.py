"""
Google Text-to-Speech integration for MediBrief.
"""

import os
import logging
import tempfile
from typing import Dict, List, Any, Optional, Tuple

from google.cloud import texttospeech
from google.oauth2 import service_account
from google.api_core.exceptions import GoogleAPIError
from pydub import AudioSegment

from utils.logger import get_logger

logger = get_logger()


class SpeechGenerator:
    """
    Google Text-to-Speech client for generating narration.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the Text-to-Speech client.

        Args:
            config: Configuration dictionary containing TTS settings.
        """
        self.language_code = config["tts"]["voice"]["language_code"]
        self.voice_name = config["tts"]["voice"]["name"]
        self.speaking_rate = config["tts"]["voice"]["speaking_rate"]
        self.pitch = config["tts"]["voice"]["pitch"]

        self.audio_encoding = getattr(
            texttospeech.AudioEncoding,
            config["tts"]["audio"]["encoding"]
        )
        self.sample_rate_hertz = config["tts"]["audio"]["sample_rate_hertz"]

        self.max_chunk_length = config["tts"]["max_chunk_length"]

        # Initialize TTS client
        self._init_tts_client(config)

    def _init_tts_client(self, config: Dict[str, Any]) -> None:
        """
        Initialize the Text-to-Speech client.

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

                self.client = texttospeech.TextToSpeechClient(credentials=credentials)
            else:
                # Initialize with default credentials
                self.client = texttospeech.TextToSpeechClient()

            logger.info("Initialized Text-to-Speech client")

        except Exception as e:
            logger.error(f"Error initializing Text-to-Speech client: {e}")
            raise

    def _split_text_into_chunks(self, text: str) -> List[str]:
        """
        Split text into chunks for TTS processing.

        Args:
            text: Text to split.

        Returns:
            List of text chunks.
        """
        # Split by sentences to avoid cutting in the middle of a sentence
        sentences = []
        current_sentence = ""

        for char in text:
            current_sentence += char

            # Check for sentence endings
            if char in ['.', '!', '?'] and len(current_sentence.strip()) > 0:
                sentences.append(current_sentence.strip())
                current_sentence = ""

        # Add the last sentence if not empty
        if current_sentence.strip():
            sentences.append(current_sentence.strip())

        # Combine sentences into chunks
        chunks = []
        current_chunk = ""

        for sentence in sentences:
            # If adding this sentence would exceed the chunk length, start a new chunk
            if len(current_chunk) + len(sentence) > self.max_chunk_length:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence
            else:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence

        # Add the last chunk if not empty
        if current_chunk:
            chunks.append(current_chunk)

        logger.info(f"Split text into {len(chunks)} chunks")
        return chunks

    def synthesize_speech(self, text: str, output_path: str) -> str:
        """
        Synthesize speech from text.

        Args:
            text: Text to synthesize.
            output_path: Path to save the audio file.

        Returns:
            Path to the generated audio file.
        """
        logger.info(f"Synthesizing speech for text: {text[:50]}...")

        try:
            # Set up voice parameters
            voice = texttospeech.VoiceSelectionParams(
                language_code=self.language_code,
                name=self.voice_name
            )

            # Set up audio parameters
            audio_config = texttospeech.AudioConfig(
                audio_encoding=self.audio_encoding,
                sample_rate_hertz=self.sample_rate_hertz,
                speaking_rate=self.speaking_rate,
                pitch=self.pitch
            )

            # Create synthesis input
            synthesis_input = texttospeech.SynthesisInput(text=text)

            # Perform text-to-speech request
            response = self.client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )

            # Write the response to the output file
            with open(output_path, "wb") as out:
                out.write(response.audio_content)

            logger.info(f"Speech synthesized and saved to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Error synthesizing speech: {e}")
            raise

    def synthesize_long_text(self, text: str, output_dir: str, output_filename: str) -> str:
        """
        Synthesize speech for a long text by splitting it into chunks.

        Args:
            text: Text to synthesize.
            output_dir: Directory to save the audio files.
            output_filename: Base filename for the output audio file.

        Returns:
            Path to the combined audio file.
        """
        logger.info(f"Synthesizing speech for long text ({len(text)} characters)")

        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        # Split text into chunks
        chunks = self._split_text_into_chunks(text)

        # Synthesize each chunk
        chunk_paths = []
        for i, chunk in enumerate(chunks):
            chunk_path = os.path.join(output_dir, f"{output_filename}_chunk_{i}.mp3")

            try:
                self.synthesize_speech(chunk, chunk_path)
                chunk_paths.append(chunk_path)
            except Exception as e:
                logger.error(f"Error synthesizing chunk {i}: {e}")

        # Combine chunks
        combined_path = os.path.join(output_dir, f"{output_filename}.mp3")
        self._combine_audio_files(chunk_paths, combined_path)

        # Clean up chunk files
        for chunk_path in chunk_paths:
            try:
                os.remove(chunk_path)
            except Exception as e:
                logger.warning(f"Error removing chunk file {chunk_path}: {e}")

        logger.info(f"Long text synthesis complete, saved to {combined_path}")
        return combined_path

    def _combine_audio_files(self, file_paths: List[str], output_path: str) -> None:
        """
        Combine multiple audio files into a single file.

        Args:
            file_paths: List of audio file paths.
            output_path: Path to save the combined audio file.
        """
        logger.info(f"Combining {len(file_paths)} audio files")

        if not file_paths:
            logger.warning("No audio files to combine")
            return

        try:
            # Load the first audio file
            combined = AudioSegment.from_file(file_paths[0])

            # Add a small pause between chunks
            pause = AudioSegment.silent(duration=500)  # 500ms pause

            # Append the rest of the audio files
            for file_path in file_paths[1:]:
                audio = AudioSegment.from_file(file_path)
                combined = combined + pause + audio

            # Export the combined audio
            combined.export(output_path, format="mp3")

            logger.info(f"Audio files combined and saved to {output_path}")

        except Exception as e:
            logger.error(f"Error combining audio files: {e}")
            raise

    def generate_narration(self, script: str, output_dir: str, output_filename: str) -> str:
        """
        Generate narration from a script.

        Args:
            script: Narration script.
            output_dir: Directory to save the audio file.
            output_filename: Filename for the output audio file.

        Returns:
            Path to the generated audio file.
        """
        logger.info("Generating narration from script")

        # Preprocess the script to improve TTS quality
        processed_script = self._preprocess_script(script)

        # Synthesize the processed script
        audio_path = self.synthesize_long_text(processed_script, output_dir, output_filename)

        return audio_path

    def _preprocess_script(self, script: str) -> str:
        """
        Preprocess the script to improve TTS quality.

        Args:
            script: Narration script.

        Returns:
            Processed script.
        """
        # Replace common abbreviations
        replacements = {
            "Fig.": "Figure",
            "et al.": "and colleagues",
            "i.e.": "that is",
            "e.g.": "for example",
            "vs.": "versus",
            "approx.": "approximately",
            "Dr.": "Doctor",
            "Prof.": "Professor"
        }

        processed_script = script
        for original, replacement in replacements.items():
            processed_script = processed_script.replace(original, replacement)

        # Add pauses (commas) around certain phrases
        pause_phrases = [
            "however", "moreover", "furthermore", "in addition",
            "consequently", "therefore", "thus", "in conclusion"
        ]

        for phrase in pause_phrases:
            processed_script = processed_script.replace(
                f" {phrase} ", f", {phrase}, "
            )

        return processed_script