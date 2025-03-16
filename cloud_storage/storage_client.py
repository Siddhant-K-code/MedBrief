"""
Google Cloud Storage integration for MediBrief.
"""

import os
import logging
from typing import Dict, List, Any, Optional, Tuple

from google.cloud import storage
from google.oauth2 import service_account
from google.api_core.exceptions import GoogleAPIError

from utils.logger import get_logger

logger = get_logger()


class StorageClient:
    """
    Google Cloud Storage client for storing videos and other assets.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the Storage client.

        Args:
            config: Configuration dictionary containing Cloud Storage settings.
        """
        self.project_id = config["api_keys"]["gcp_project_id"]

        # Bucket names
        self.video_bucket = config["cloud_storage"]["buckets"]["videos"]
        self.pdf_bucket = config["cloud_storage"]["buckets"]["pdfs"]
        self.image_bucket = config["cloud_storage"]["buckets"]["images"]
        self.audio_bucket = config["cloud_storage"]["buckets"]["audio"]

        # Storage settings
        self.storage_class = config["cloud_storage"]["storage_class"]
        self.retention_days = config["cloud_storage"]["retention_days"]

        # Initialize Storage client
        self._init_storage_client(config)

    def _init_storage_client(self, config: Dict[str, Any]) -> None:
        """
        Initialize the Storage client.

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

                self.client = storage.Client(
                    project=self.project_id,
                    credentials=credentials
                )
            else:
                # Initialize with default credentials
                self.client = storage.Client(project=self.project_id)

            logger.info(f"Initialized Storage client for project {self.project_id}")

        except Exception as e:
            logger.error(f"Error initializing Storage client: {e}")
            raise

    def _get_bucket(self, bucket_name: str) -> storage.Bucket:
        """
        Get a bucket by name.

        Args:
            bucket_name: Name of the bucket.

        Returns:
            Bucket object.

        Raises:
            Exception: If the bucket does not exist.
        """
        try:
            bucket = self.client.get_bucket(bucket_name)
            return bucket
        except GoogleAPIError as e:
            logger.error(f"Error getting bucket {bucket_name}: {e}")
            raise

    def upload_file(self, source_path: str, destination_blob_name: str, bucket_name: str) -> str:
        """
        Upload a file to Cloud Storage.

        Args:
            source_path: Path to the source file.
            destination_blob_name: Name of the destination blob.
            bucket_name: Name of the bucket.

        Returns:
            Public URL of the uploaded file.

        Raises:
            Exception: If the upload fails.
        """
        logger.info(f"Uploading {source_path} to {bucket_name}/{destination_blob_name}")

        try:
            # Get the bucket
            bucket = self._get_bucket(bucket_name)

            # Create a blob
            blob = bucket.blob(destination_blob_name)

            # Set storage class
            blob.storage_class = self.storage_class

            # Upload the file
            blob.upload_from_filename(source_path)

            # Make the blob publicly accessible
            blob.make_public()

            # Get the public URL
            public_url = blob.public_url

            logger.info(f"File uploaded to {public_url}")
            return public_url

        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            raise

    def upload_video(self, video_path: str, video_name: str) -> str:
        """
        Upload a video to Cloud Storage.

        Args:
            video_path: Path to the video file.
            video_name: Name for the video in Cloud Storage.

        Returns:
            Public URL of the uploaded video.
        """
        return self.upload_file(video_path, video_name, self.video_bucket)

    def upload_pdf(self, pdf_path: str, pdf_name: str) -> str:
        """
        Upload a PDF to Cloud Storage.

        Args:
            pdf_path: Path to the PDF file.
            pdf_name: Name for the PDF in Cloud Storage.

        Returns:
            Public URL of the uploaded PDF.
        """
        return self.upload_file(pdf_path, pdf_name, self.pdf_bucket)

    def upload_image(self, image_path: str, image_name: str) -> str:
        """
        Upload an image to Cloud Storage.

        Args:
            image_path: Path to the image file.
            image_name: Name for the image in Cloud Storage.

        Returns:
            Public URL of the uploaded image.
        """
        return self.upload_file(image_path, image_name, self.image_bucket)

    def upload_audio(self, audio_path: str, audio_name: str) -> str:
        """
        Upload an audio file to Cloud Storage.

        Args:
            audio_path: Path to the audio file.
            audio_name: Name for the audio file in Cloud Storage.

        Returns:
            Public URL of the uploaded audio file.
        """
        return self.upload_file(audio_path, audio_name, self.audio_bucket)

    def download_file(self, source_blob_name: str, destination_path: str, bucket_name: str) -> str:
        """
        Download a file from Cloud Storage.

        Args:
            source_blob_name: Name of the source blob.
            destination_path: Path to save the downloaded file.
            bucket_name: Name of the bucket.

        Returns:
            Path to the downloaded file.

        Raises:
            Exception: If the download fails.
        """
        logger.info(f"Downloading {bucket_name}/{source_blob_name} to {destination_path}")

        try:
            # Get the bucket
            bucket = self._get_bucket(bucket_name)

            # Get the blob
            blob = bucket.blob(source_blob_name)

            # Download the file
            blob.download_to_filename(destination_path)

            logger.info(f"File downloaded to {destination_path}")
            return destination_path

        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            raise

    def list_files(self, bucket_name: str, prefix: Optional[str] = None) -> List[str]:
        """
        List files in a bucket.

        Args:
            bucket_name: Name of the bucket.
            prefix: Optional prefix to filter files.

        Returns:
            List of file names.
        """
        logger.info(f"Listing files in {bucket_name}" + (f" with prefix {prefix}" if prefix else ""))

        try:
            # Get the bucket
            bucket = self._get_bucket(bucket_name)

            # List blobs
            blobs = bucket.list_blobs(prefix=prefix)

            # Get blob names
            blob_names = [blob.name for blob in blobs]

            logger.info(f"Found {len(blob_names)} files")
            return blob_names

        except Exception as e:
            logger.error(f"Error listing files: {e}")
            return []

    def delete_file(self, blob_name: str, bucket_name: str) -> bool:
        """
        Delete a file from Cloud Storage.

        Args:
            blob_name: Name of the blob to delete.
            bucket_name: Name of the bucket.

        Returns:
            True if the file was deleted, False otherwise.
        """
        logger.info(f"Deleting {bucket_name}/{blob_name}")

        try:
            # Get the bucket
            bucket = self._get_bucket(bucket_name)

            # Get the blob
            blob = bucket.blob(blob_name)

            # Delete the blob
            blob.delete()

            logger.info(f"File {blob_name} deleted")
            return True

        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return False

    def create_bucket_if_not_exists(self, bucket_name: str) -> storage.Bucket:
        """
        Create a bucket if it does not exist.

        Args:
            bucket_name: Name of the bucket.

        Returns:
            Bucket object.
        """
        logger.info(f"Checking if bucket {bucket_name} exists")

        try:
            # Try to get the bucket
            bucket = self.client.get_bucket(bucket_name)
            logger.info(f"Bucket {bucket_name} already exists")
            return bucket

        except GoogleAPIError:
            # Bucket does not exist, create it
            logger.info(f"Creating bucket {bucket_name}")

            bucket = self.client.create_bucket(bucket_name)

            # Set lifecycle rules for automatic deletion
            lifecycle_rules = [
                {
                    "action": {"type": "Delete"},
                    "condition": {"age": self.retention_days}
                }
            ]

            bucket.lifecycle_rules = lifecycle_rules
            bucket.patch()

            logger.info(f"Bucket {bucket_name} created with {self.retention_days} day retention")
            return bucket

    def ensure_buckets_exist(self) -> None:
        """
        Ensure that all required buckets exist.
        """
        logger.info("Ensuring all required buckets exist")

        self.create_bucket_if_not_exists(self.video_bucket)
        self.create_bucket_if_not_exists(self.pdf_bucket)
        self.create_bucket_if_not_exists(self.image_bucket)
        self.create_bucket_if_not_exists(self.audio_bucket)