"""
A robust, dual-engine service to interact with a Large Language Model (LLM).
"""
import os
import sys
import json
from typing import List, Iterator
from dotenv import load_dotenv
import openai
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential

load_dotenv()

# --- Provider Configuration ---
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_MODEL_NAME = "microsoft/Phi-3-small-128k-instruct"
GITHUB_API_ENDPOINT = "https://models.github.ai/inference"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_MODEL_NAME = "deepseek-r1:14b"

class LLMProvider:
    """A dual-engine provider for GitHub Models with an Ollama fallback."""
    def __init__(self):
        self.github_client = None
        self.ollama_client = None
        if GITHUB_TOKEN:
            try:
                self.github_client = ChatCompletionsClient(endpoint=GITHUB_API_ENDPOINT, credential=AzureKeyCredential(GITHUB_TOKEN))
                print(f"LLMProvider: GitHub Models client initialized.")
            except Exception as e:
                print(f"Warning: Failed to initialize GitHub Models client: {e}", file=sys.stderr)
        if OLLAMA_BASE_URL:
            try:
                self.ollama_client = openai.OpenAI(base_url=OLLAMA_BASE_URL, api_key='ollama')
                print(f"LLMProvider: Ollama fallback client initialized.")
            except Exception as e:
                print(f"Warning: Failed to initialize Ollama client: {e}", file=sys.stderr)

    def generate_streamed_response(
        self,
        system_prompt: str,
        user_message: str,
        context_rules: List[str]
    ) -> Iterator[str]:
        """Generates a streamed response from the configured GitHub Model."""
        if not self.client:
            yield "Error: LLM client is not initialized."
            return

        context = "\n".join(f"<rule>{rule}</rule>" for rule in context_rules)
        messages = [
            SystemMessage(content=system_prompt),
            UserMessage(content=f"<context>\n{context}\n</context>\n\nQuestion: {user_message}")
        ]
        
        try:
            print(f"Streaming request to GitHub Models (model: {GITHUB_MODEL_NAME})...")
            # This call now mirrors the exact structure from the documentation.
            stream = self.client.complete(
                messages=messages,
                model=GITHUB_MODEL_NAME,
                temperature=0.1,
                stream=True,
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except ClientAuthenticationError as e:
            yield f"Authentication Error: The provided GitHub token is invalid, expired, or does not have 'models_read' scope. Details: {e}"
        except HttpResponseError as e:
            # This will catch the 'no_access' error and provide more detail.
            yield f"API Error: Received an error from the GitHub Models API. This may be an access issue. Details: {e.message}"
        except Exception as e:
            print(f"An unexpected error occurred during LLM streaming: {e}", file=sys.stderr)
            yield f"An unexpected error occurred with the AI provider: {e}"

    # --- NEW: Method for generating structured JSON ---
    def generate_json_response(self, system_prompt: str, user_message: str) -> str:
        """
        Generates a structured JSON response from the LLM.
        It prioritizes the GitHub model and falls back to Ollama.
        """
        messages = [
            SystemMessage(content=system_prompt),
            UserMessage(content=user_message)
        ]
        
        # Prioritize GitHub Client for its likely better JSON-following capabilities
        if self.github_client:
            try:
                print(f"Generating JSON with GitHub Models (model: {GITHUB_MODEL_NAME})...")
                # Azure SDK uses `response_format` in `model_extras`
                response = self.github_client.complete(
                    model=GITHUB_MODEL_NAME,
                    messages=messages,
                    temperature=0.0,
                    response_format={"type": "json_object"}
                )
                return response.choices[0].message.content or "{}"
            except Exception as e:
                print(f"Warning: GitHub Models JSON generation failed: {e}", file=sys.stderr)
                print("Falling back to Ollama for JSON generation...")

        # Fallback to Ollama
        if self.ollama_client:
            try:
                print(f"Generating JSON with Ollama (model: {OLLAMA_MODEL_NAME})...")
                # OpenAI SDK uses `response_format` directly
                response = self.ollama_client.chat.completions.create(
                    model=OLLAMA_MODEL_NAME,
                    messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
                    temperature=0.0,
                    response_format={"type": "json_object"}
                )
                return response.choices[0].message.content or "{}"
            except Exception as e:
                print(f"ERROR: Ollama JSON generation also failed: {e}", file=sys.stderr)
                raise
        
        raise RuntimeError("No available LLM provider could generate a JSON response.")

llm_provider = LLMProvider()