"""
A service to interact with a Large Language Model (LLM).

This module provides a pluggable provider for generating text using an LLM.
It is configured to connect to a local Ollama instance that serves models via
an OpenAI-compatible API endpoint. This allows for easy integration using the
standard 'openai' library while keeping all processing local and free.
"""

import os
import sys
from typing import List
from dotenv import load_dotenv
from openai import OpenAI, APIConnectionError

# Load environment variables from the .env file in the project root.
load_dotenv()

class LLMProvider:
    """A provider class for generating responses from a local LLM via Ollama."""

    def __init__(self):
        """
        Initializes the LLMProvider.
        
        It configures the OpenAI client to point to the local Ollama server
        using the base URL specified in the .env file.
        """
        self.client = None
        ollama_base_url = os.getenv("OLLAMA_BASE_URL")
        if not ollama_base_url:
            print("FATAL: OLLAMA_BASE_URL environment variable is not set.", file=sys.stderr)
            print("Please add OLLAMA_BASE_URL=http://localhost:11434 to your .env file.", file=sys.stderr)
            # Exit here because the application cannot function without this setting.
            sys.exit(1)
        
        try:
            # Configure the OpenAI client to connect to the local Ollama instance.
            # The API key is not required by Ollama but the library expects a value.
            self.client = OpenAI(
                base_url=ollama_base_url,
                api_key='ollama',
            )
            print("LLMProvider initialized. Connected to Ollama server.")
        except Exception as e:
            print(f"FATAL: Failed to initialize OpenAI client for Ollama: {e}", file=sys.stderr)
            sys.exit(1)

    def generate_response(
        self,
        system_prompt: str,
        user_message: str,
        context_rules: List[str],
        model: str = "phi3:mini"
    ) -> str:
        """
        Generates a response from the LLM using a provided context.

        Args:
            system_prompt: The instruction prompt for the system role.
            user_message: The user's query.
            context_rules: A list of relevant rule texts retrieved from the RAG store.
            model: The name of the model to use (e.g., 'llama3:8b', 'phi3:mini').

        Returns:
            The text content of the LLM's generated response.
        """

        # Format the prompt with clear, XML-like tags to separate the context from the user's actual question.
        formatted_context = "\n".join(f"<rule>{rule}</rule>" for rule in context_rules)

        prompt_with_context = (
            "<context>\n"
            f"{formatted_context}\n"
            "</context>\n\n"
            f"Question: {user_message}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_with_context},
        ]

        try:
            print(f"Sending request to LLM (model: {model})...")
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.2, # Lower temperature for more deterministic, factual answers.
            )
            return response.choices[0].message.content or "No response content."
        except APIConnectionError as e:
            error_message = (
                "LLM Connection Error: Could not connect to the Ollama server. "
                "Please ensure Ollama is running and the OLLAMA_BASE_URL is correct."
            )
            print(f"ERROR: {error_message} - {e}", file=sys.stderr)
            return error_message
        except Exception as e:
            print(f"An unexpected error occurred during LLM generation: {e}", file=sys.stderr)
            return "An unexpected error occurred while generating the response."

# Singleton instance for use across the application.
llm_provider = LLMProvider()