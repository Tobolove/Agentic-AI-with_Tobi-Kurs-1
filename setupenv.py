import os
from openai import AzureOpenAI
from dotenv import load_dotenv

# Load environment variables and initialize OpenAI client
load_dotenv()

# Azure OpenAI Configuration - following the pattern you showed
api_key = os.getenv("AZURE_OPENAI_API_KEY")
azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")

# Model name should match your Azure deployment name
model = azure_deployment if azure_deployment else "gpt-4o-mini"

if not api_key or not azure_endpoint:
    raise ValueError("Azure OpenAI configuration missing. Please set AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, and AZURE_OPENAI_DEPLOYMENT_NAME in your .env file.")

# Configure client for Azure OpenAI
client = AzureOpenAI(
    api_key=api_key,
    api_version=api_version,
    azure_endpoint=azure_endpoint,
)

# --- Helper Function for API Calls ---
def call_openai(system_prompt, user_prompt, model=model):
    """Simple wrapper for OpenAI API calls."""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"An error occurred: {e}"