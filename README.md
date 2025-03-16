# MediBrief

MediBrief is an automated system that summarizes medical research papers into concise, informative videos. The system fetches papers from PubMed, processes them, and creates professional videos with narration that are automatically uploaded to YouTube.

## Features

- PubMed API integration for fetching the latest medical research papers
- PDF processing to extract text, figures, and tables
- AI-powered summarization using Google Vertex AI (Gemini)
- Image analysis to select and process relevant figures
- Text-to-Speech narration generation
- Automated video creation with MoviePy
- YouTube upload integration
- Fully automated pipeline with Google Cloud Functions
- **[TODO]** Enhanced video generation with Runway Gen-2 API

## Planned Features

- AI-generated video content using Runway Gen-2 API
- Automated subtitle generation
- Enhanced visual storytelling with AI-generated scenes
- Improved integration of paper figures with generated content

## System Requirements

- Python 3.9+
- Google Cloud Platform account
- API keys for:
  - PubMed/NCBI E-utilities
  - Google Vertex AI
  - Google Cloud Storage
  - Google Text-to-Speech
  - YouTube Data API
  - Runway Gen-2 API (for enhanced video generation)

## Installation

1. Clone the repository:

```sh
git clone https://github.com/Siddhant-K-code/MediBrief.git
cd MediBrief
```

2. Create and activate a virtual environment:

```sh
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```sh
pip install -r requirements.txt
```

4. Set up configuration:

```sh
cp config.example.yaml config.yaml
```

Then edit `config.yaml` with your API keys and preferences.

## Usage

### Local Development

To run the system locally:

```sh
python main.py
```

### Deployment

Follow the deployment instructions in `docs/deployment.md` to set up the system on Google Cloud Platform.

## Project Structure

- `pubmed/`: PubMed API integration
- `pdf_processing/`: PDF extraction and processing
- `ai_processing/`: Vertex AI integration for summarization
- `image_analysis/`: Vision AI for figure analysis
- `tts/`: Text-to-Speech integration
- `video_generation/`: Video creation (MoviePy and Runway Gen-2)
- `cloud_storage/`: Google Cloud Storage integration
- `youtube/`: YouTube upload functionality
- `pipeline/`: Orchestration and automation
- `config/`: Configuration files
- `utils/`: Utility functions
- `tests/`: Unit and integration tests
- `docs/`: Documentation
- `TODO.md`: Planned enhancements and features
