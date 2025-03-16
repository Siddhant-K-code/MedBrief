# MediBrief Deployment Guide

This guide provides instructions for deploying the MediBrief system on Google Cloud Platform (GCP).

## Prerequisites

Before deploying MediBrief, you need:

1. A Google Cloud Platform account with billing enabled
2. The following APIs enabled in your GCP project:
   - Cloud Functions API
   - Cloud Scheduler API
   - Cloud Storage API
   - Vertex AI API
   - Vision API
   - Text-to-Speech API
   - YouTube Data API v3
3. A service account with appropriate permissions
4. YouTube OAuth 2.0 credentials

## Step 1: Set Up Service Account

1. Go to the [GCP Console](https://console.cloud.google.com/)
2. Navigate to "IAM & Admin" > "Service Accounts"
3. Click "Create Service Account"
4. Enter a name (e.g., "medbrief-service-account") and description
5. Grant the following roles:
   - Storage Admin
   - Cloud Functions Admin
   - Cloud Scheduler Admin
   - Vertex AI User
   - Cloud Vision API User
   - Cloud Text-to-Speech API User
6. Click "Create and Continue"
7. Create a key for the service account (JSON format)
8. Download and securely store the key file

## Step 2: Set Up YouTube OAuth Credentials

1. Go to the [Google API Console](https://console.developers.google.com/)
2. Navigate to "Credentials"
3. Click "Create Credentials" > "OAuth client ID"
4. Select "Desktop app" as the application type
5. Enter a name (e.g., "MediBrief YouTube Uploader")
6. Download the client secrets JSON file
7. Rename it to `client_secrets.json`

## Step 3: Configure MediBrief

1. Create a `config.yaml` file based on the `config.example.yaml` template
2. Update the following settings:
   - `api_keys.gcp_project_id`: Your GCP project ID
   - `api_keys.gcp_service_account_key`: Path to your service account key file
   - `api_keys.pubmed`: Your PubMed API key
   - `youtube.channel_id`: Your YouTube channel ID
   - `youtube.client_secrets_path`: Path to your `client_secrets.json` file
   - Adjust other settings as needed

## Step 4: Create Cloud Storage Buckets

The system will automatically create the required buckets if they don't exist, but you can also create them manually:

1. Go to the [GCP Console](https://console.cloud.google.com/)
2. Navigate to "Cloud Storage" > "Buckets"
3. Click "Create Bucket"
4. Create the following buckets (use the names specified in your config.yaml):
   - `medbrief-videos`
   - `medbrief-pdfs`
   - `medbrief-images`
   - `medbrief-audio`
5. Set appropriate access controls and lifecycle rules

## Step 5: Deploy as a Cloud Function

1. Prepare your code for deployment:

```bash
# Create a deployment package
mkdir deploy
cp -r *.py *.yaml requirements.txt pubmed/ pdf_processing/ ai_processing/ image_analysis/ tts/ video_generation/ cloud_storage/ youtube/ pipeline/ utils/ deploy/
cd deploy
```

2. Create a `main.py` file in the deployment directory:

```python
from pipeline.orchestrator import Orchestrator
from utils.config_loader import load_config

def medbrief_function(event, context):
    """Cloud Function entry point."""
    # Load configuration
    config = load_config("config.yaml")

    # Initialize orchestrator
    orchestrator = Orchestrator(config)

    # Run the pipeline
    orchestrator.run()

    return "MediBrief pipeline completed successfully"
```

3. Deploy the Cloud Function:

```bash
gcloud functions deploy medbrief \
  --runtime python39 \
  --trigger-topic medbrief-trigger \
  --memory 2048MB \
  --timeout 540s \
  --service-account YOUR_SERVICE_ACCOUNT@YOUR_PROJECT.iam.gserviceaccount.com
```

## Step 6: Set Up Cloud Scheduler

1. Go to the [GCP Console](https://console.cloud.google.com/)
2. Navigate to "Cloud Scheduler"
3. Click "Create Job"
4. Configure the job:
   - Name: `medbrief-daily`
   - Frequency: `0 0 * * *` (daily at midnight)
   - Target: Pub/Sub
   - Topic: `medbrief-trigger`
   - Message: `{"run": true}`
5. Click "Create"

## Step 7: YouTube Authentication

The first time the function runs, it will need YouTube authentication:

1. Run the function locally first:

```bash
python main.py
```

2. Follow the OAuth flow to authenticate with YouTube
3. The credentials will be saved to `youtube_credentials.json`
4. Upload this file to your Cloud Function:

```bash
gcloud functions deploy medbrief \
  --update-env-vars YOUTUBE_CREDENTIALS=youtube_credentials.json
```

## Step 8: Monitor and Troubleshoot

1. Go to the [GCP Console](https://console.cloud.google.com/)
2. Navigate to "Cloud Functions" > "medbrief" > "Logs"
3. Monitor the logs for any errors or issues
4. Check the Cloud Storage buckets for output files
5. Verify that videos are being uploaded to YouTube

## Additional Configuration

### Scaling Up

For processing more papers:

1. Increase the `max_concurrent_papers` setting in your config.yaml
2. Increase the memory and timeout for your Cloud Function:

```bash
gcloud functions deploy medbrief \
  --memory 4096MB \
  --timeout 540s
```

### Cost Optimization

To optimize costs:

1. Adjust the `time_period_days` and `max_results_per_query` settings
2. Set appropriate retention policies for Cloud Storage buckets
3. Consider using a lower-tier Vertex AI model
4. Run the pipeline less frequently (e.g., weekly instead of daily)

## Troubleshooting

### Common Issues

1. **YouTube Authentication Errors**: Ensure your OAuth credentials are valid and properly configured
2. **API Quota Exceeded**: Check your API usage and consider increasing quotas
3. **Timeout Errors**: Increase the Cloud Function timeout or reduce the number of papers processed
4. **Memory Errors**: Increase the Cloud Function memory allocation

### Getting Help

If you encounter issues:

1. Check the Cloud Function logs for detailed error messages
2. Review the MediBrief documentation
3. Check the GCP documentation for specific services
4. Contact support if needed