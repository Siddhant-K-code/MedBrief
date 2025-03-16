"""
YouTube API integration for MediBrief.
"""

import os
import logging
import time
import http.client
import httplib2
import random
import json
from typing import Dict, List, Any, Optional, Tuple

import google.oauth2.credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from utils.logger import get_logger

logger = get_logger()

# This OAuth 2.0 access scope allows an application to upload files to the
# authenticated user's YouTube channel, but doesn't allow other types of access.
YOUTUBE_UPLOAD_SCOPE = ["https://www.googleapis.com/auth/youtube.upload"]
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"


class YouTubeUploader:
    """
    YouTube API client for uploading videos.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the YouTube uploader.

        Args:
            config: Configuration dictionary containing YouTube settings.
        """
        self.channel_id = config["youtube"]["channel_id"]
        self.category_id = config["youtube"]["video"]["category_id"]
        self.privacy_status = config["youtube"]["video"]["privacy_status"]
        self.tags = config["youtube"]["video"]["tags"]
        self.description_template = config["youtube"]["description_template"]

        # Check if dry run mode is enabled
        self.dry_run = config["youtube"].get("dry_run", False)

        # Initialize YouTube API client
        self._init_youtube_client(config)

    def _init_youtube_client(self, config: Dict[str, Any]) -> None:
        """
        Initialize the YouTube API client.

        Args:
            config: Configuration dictionary.
        """
        try:
            # Get credentials
            credentials = self._get_credentials(config)

            # Build the YouTube API client
            self.youtube = build(
                YOUTUBE_API_SERVICE_NAME,
                YOUTUBE_API_VERSION,
                credentials=credentials
            )

            logger.info("Initialized YouTube API client")

        except Exception as e:
            logger.error(f"Error initializing YouTube API client: {e}")
            raise

    def _get_credentials(self, config: Dict[str, Any]) -> google.oauth2.credentials.Credentials:
        """
        Get OAuth 2.0 credentials for the YouTube API.

        Args:
            config: Configuration dictionary.

        Returns:
            OAuth 2.0 credentials.

        Raises:
            Exception: If credentials cannot be obtained.
        """
        # Check if credentials are stored in a file
        credentials_path = config["youtube"].get("credentials_path", "youtube_credentials.json")
        client_secrets_path = config["youtube"].get("client_secrets_path", "client_secrets.json")

        credentials = None

        # Load credentials from file if it exists
        if os.path.exists(credentials_path):
            try:
                with open(credentials_path, "r") as f:
                    creds_data = json.load(f)

                credentials = google.oauth2.credentials.Credentials(
                    token=creds_data.get("token"),
                    refresh_token=creds_data.get("refresh_token"),
                    token_uri=creds_data.get("token_uri"),
                    client_id=creds_data.get("client_id"),
                    client_secret=creds_data.get("client_secret"),
                    scopes=YOUTUBE_UPLOAD_SCOPE
                )
            except Exception as e:
                logger.warning(f"Error loading credentials from file: {e}")

        # If credentials don't exist or are invalid, get new ones
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                # Refresh credentials
                try:
                    credentials.refresh(Request())
                except Exception as e:
                    logger.warning(f"Error refreshing credentials: {e}")
                    credentials = None

            # If still no valid credentials, get new ones
            if not credentials:
                if not os.path.exists(client_secrets_path):
                    raise FileNotFoundError(
                        f"Client secrets file not found: {client_secrets_path}. "
                        "Please download it from the Google API Console."
                    )

                # Get credentials from user
                flow = InstalledAppFlow.from_client_secrets_file(
                    client_secrets_path, YOUTUBE_UPLOAD_SCOPE
                )

                credentials = flow.run_local_server(port=8090)

                # Save credentials for future use
                creds_data = {
                    "token": credentials.token,
                    "refresh_token": credentials.refresh_token,
                    "token_uri": credentials.token_uri,
                    "client_id": credentials.client_id,
                    "client_secret": credentials.client_secret,
                    "scopes": credentials.scopes
                }

                with open(credentials_path, "w") as f:
                    json.dump(creds_data, f)

                logger.info(f"Saved credentials to {credentials_path}")

        return credentials

    def format_description(self, paper_data: Dict[str, Any], key_takeaways: List[str]) -> str:
        """
        Format the video description using the template.

        Args:
            paper_data: Dictionary containing paper data.
            key_takeaways: List of key takeaways.

        Returns:
            Formatted description.
        """
        # Format key takeaways as a bulleted list
        takeaways_text = "\n".join([f"• {takeaway}" for takeaway in key_takeaways])

        # Format the description
        description = self.description_template.format(
            title=paper_data.get("title", "Unknown Title"),
            authors=", ".join(paper_data.get("authors", ["Unknown Authors"])),
            journal=paper_data.get("journal", "Unknown Journal"),
            publication_date=paper_data.get("publication_date", "Unknown Date"),
            doi=paper_data.get("doi", ""),
            key_takeaways=takeaways_text
        )

        return description

    def upload_video(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Upload a video to YouTube.

        Args:
            video_path: Path to the video file.
            title: Video title.
            description: Video description.
            tags: List of tags for the video.

        Returns:
            Dictionary containing upload results.
        """
        if self.dry_run:
            logger.info(f"DRY RUN: Would upload {video_path} with title: {title}")
            return {
                "id": "dry_run_video_id",
                "title": title,
                "url": "https://www.youtube.com/watch?v=dry_run_video_id"
            }

        logger.info(f"Uploading video: {video_path}")

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        if tags is None:
            tags = self.tags

        # Create a media upload object
        media = MediaFileUpload(
            video_path,
            mimetype="video/mp4",
            resumable=True
        )

        # Set up the video metadata
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": self.category_id
            },
            "status": {
                "privacyStatus": self.privacy_status,
                "selfDeclaredMadeForKids": False
            }
        }

        # Call the API to upload the video
        try:
            upload_request = self.youtube.videos().insert(
                part=",".join(body.keys()),
                body=body,
                media_body=media
            )

            # Upload the video with progress tracking
            response = self._upload_with_progress(upload_request)

            video_id = response.get("id")
            video_url = f"https://www.youtube.com/watch?v={video_id}"

            logger.info(f"Video uploaded successfully: {video_url}")

            return {
                "id": video_id,
                "title": title,
                "url": video_url
            }

        except HttpError as e:
            logger.error(f"Error uploading video: {e}")
            raise

    def _upload_with_progress(self, request) -> Dict[str, Any]:
        """
        Upload a video with progress tracking.

        Args:
            request: YouTube API upload request.

        Returns:
            Response from the API.
        """
        response = None
        error = None
        retry = 0
        max_retries = 10

        while response is None:
            try:
                status, response = request.next_chunk()
                if status:
                    percent = int(status.progress() * 100)
                    logger.info(f"Upload progress: {percent}%")

            except HttpError as e:
                if e.resp.status in [500, 502, 503, 504]:
                    # Retry on server errors
                    if retry < max_retries:
                        retry += 1
                        sleep_time = random.randint(1, 2 ** retry)
                        logger.warning(f"Upload failed with server error, retrying in {sleep_time} seconds...")
                        time.sleep(sleep_time)
                    else:
                        logger.error(f"Upload failed after {max_retries} retries")
                        raise
                else:
                    # Other errors are not retried
                    logger.error(f"Upload failed with client error: {e}")
                    raise

            except (httplib2.HttpLib2Error, http.client.HTTPException) as e:
                # Network errors are retried
                if retry < max_retries:
                    retry += 1
                    sleep_time = random.randint(1, 2 ** retry)
                    logger.warning(f"Upload failed with network error, retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"Upload failed after {max_retries} retries")
                    raise

        return response

    def process_and_upload_video(
        self,
        video_path: str,
        paper_data: Dict[str, Any],
        key_takeaways: List[str]
    ) -> Dict[str, Any]:
        """
        Process and upload a video to YouTube.

        Args:
            video_path: Path to the video file.
            paper_data: Dictionary containing paper data.
            key_takeaways: List of key takeaways.

        Returns:
            Dictionary containing upload results.
        """
        # Generate title
        title = paper_data.get("title", "Unknown Title")

        # Truncate title if it's too long (YouTube limit is 100 characters)
        if len(title) > 95:
            title = title[:92] + "..."

        # Format description
        description = self.format_description(paper_data, key_takeaways)

        # Upload the video
        result = self.upload_video(video_path, title, description, self.tags)

        return result