"""
Hunyuan3D API Client

A Python client for the Hunyuan3D 2.1 API server that provides endpoints for generating 3D models from 2D images.
"""

import base64
import json
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import requests
from requests.exceptions import RequestException


class TaskStatus(str, Enum):
    """Enumeration of possible task statuses."""
    COMPLETED = "completed"
    PROCESSING = "processing"
    TEXTURING = "texturing"
    ERROR = "error"


@dataclass
class GenerationRequest:
    """Request model for 3D generation API."""
    image: str  # Base64 encoded input image
    remove_background: bool = True
    texture: bool = False
    seed: int = 1234
    octree_resolution: int = 256
    num_inference_steps: int = 5
    guidance_scale: float = 5.0
    num_chunks: int = 8000
    face_count: int = 40000

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API request."""
        return {
            "image": self.image,
            "remove_background": self.remove_background,
            "texture": self.texture,
            "seed": self.seed,
            "octree_resolution": self.octree_resolution,
            "num_inference_steps": self.num_inference_steps,
            "guidance_scale": self.guidance_scale,
            "num_chunks": self.num_chunks,
            "face_count": self.face_count
        }

    @classmethod
    def from_image_file(cls, image_path: str, **kwargs) -> 'GenerationRequest':
        """Create a GenerationRequest from an image file."""
        with open(image_path, 'rb') as f:
            image_data = f.read()

        # The server expects pure base64 data, not data URL format
        base64_image = base64.b64encode(image_data).decode('utf-8')

        return cls(image=base64_image, **kwargs)


@dataclass
class GenerationResponse:
    """Response model for generation status."""
    uid: str


@dataclass
class HealthResponse:
    """Response model for health check."""
    status: str
    worker_id: str


@dataclass
class StatusResponse:
    """Response model for status endpoint."""
    status: str
    model_base64: Optional[str] = None
    message: Optional[str] = None


@dataclass
class ValidationError:
    """Validation error details."""
    loc: list
    msg: str
    type: str


@dataclass
class HTTPValidationError:
    """HTTP validation error response."""
    detail: list[ValidationError]


class Hunyuan3DAPIError(Exception):
    """Base exception for Hunyuan3D API errors."""
    pass


class Hunyuan3DAPIValidationError(Hunyuan3DAPIError):
    """Exception raised for validation errors."""
    def __init__(self, validation_errors: list[ValidationError]):
        self.validation_errors = validation_errors
        super().__init__(
            f"Validation errors: {[error.msg for error in validation_errors]}"
        )


class Hunyuan3DAPIClient:
    """
    Client for the Hunyuan3D 2.1 API Server.

    This client provides methods to interact with the Hunyuan3D API for generating
    3D models from 2D images, checking task status, and monitoring service health.
    """

    def __init__(self, base_url: str = "http://localhost:8081", timeout: int = 30):
        """
        Initialize the Hunyuan3D API client.

        Args:
            base_url: Base URL of the Hunyuan3D API server
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()

        # Set default headers
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Make an HTTP request to the API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            **kwargs: Additional arguments for requests

        Returns:
            Response data as dictionary

        Raises:
            Hunyuan3DAPIError: For API errors
            Hunyuan3DAPIValidationError: For validation errors
        """
        url = f"{self.base_url}{endpoint}"

        try:
            response = self.session.request(
                method=method,
                url=url,
                timeout=self.timeout,
                **kwargs
            )
            response.raise_for_status()

            # Handle empty responses
            if response.status_code == 200 and not response.content:
                return {}

            return response.json()

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 422:
                # Validation error
                try:
                    error_data = e.response.json()
                    validation_errors = [
                        ValidationError(**error)
                        for error in error_data.get('detail', [])
                    ]
                    raise Hunyuan3DAPIValidationError(validation_errors)
                except (KeyError, TypeError, ValueError):
                    raise Hunyuan3DAPIError(
                        f"Validation error: {e.response.text}"
                    )
            else:
                raise Hunyuan3DAPIError(
                    f"HTTP error {e.response.status_code}: {e.response.text}"
                )
        except RequestException as e:
            raise Hunyuan3DAPIError(f"Request failed: {str(e)}")
        except json.JSONDecodeError as e:
            raise Hunyuan3DAPIError(f"Invalid JSON response: {str(e)}")

    def health_check(self) -> HealthResponse:
        """
        Check the health status of the Hunyuan3D API server.

        Returns:
            HealthResponse: Service health status and worker identifier

        Raises:
            Hunyuan3DAPIError: If the health check fails
        """
        data = self._make_request('GET', '/health')
        return HealthResponse(**data)

    def generate_3d_model(self, request: GenerationRequest) -> bytes:
        """
        Generate a 3D model from an input image synchronously.

        This endpoint takes an image and generates a 3D model with optional textures.
        The generation process includes background removal, mesh generation, and optional texture mapping.

        Args:
            request: GenerationRequest containing the image and generation parameters

        Returns:
            bytes: The generated 3D model file (GLB or OBJ format)

        Raises:
            Hunyuan3DAPIError: If the generation fails
            Hunyuan3DAPIValidationError: If the request parameters are invalid
        """
        url = f"{self.base_url}/generate"

        try:
            response = self.session.post(
                url,
                json=request.to_dict(),
                timeout=self.timeout
            )
            response.raise_for_status()

            # The /generate endpoint returns the file directly
            return response.content

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 422:
                # Validation error
                try:
                    error_data = e.response.json()
                    validation_errors = [
                        ValidationError(**error)
                        for error in error_data.get('detail', [])
                    ]
                    raise Hunyuan3DAPIValidationError(validation_errors)
                except (KeyError, TypeError, ValueError):
                    raise Hunyuan3DAPIError(
                        f"Validation error: {e.response.text}"
                    )
            else:
                raise Hunyuan3DAPIError(
                    f"HTTP error {e.response.status_code}: {e.response.text}"
                )
        except RequestException as e:
            raise Hunyuan3DAPIError(f"Request failed: {str(e)}")

    def send_generation_task(self, request: GenerationRequest) -> GenerationResponse:
        """
        Send a 3D generation task to be processed asynchronously.

        This endpoint starts the generation process in the background and returns a task ID.
        Use the status() method to check the progress and retrieve the result.

        Args:
            request: GenerationRequest containing the image and generation parameters

        Returns:
            GenerationResponse: Contains the unique task identifier

        Raises:
            Hunyuan3DAPIError: If the task submission fails
            Hunyuan3DAPIValidationError: If the request parameters are invalid
        """
        data = self._make_request('POST', '/send', json=request.to_dict())
        return GenerationResponse(**data)

    def get_task_status(self, uid: str) -> StatusResponse:
        """
        Check the status of a generation task.

        Args:
            uid: The unique identifier of the generation task

        Returns:
            StatusResponse: Current status of the task and result if completed

        Raises:
            Hunyuan3DAPIError: If the status check fails
        """
        data = self._make_request('GET', f'/status/{uid}')
        return StatusResponse(**data)

    def wait_for_completion(self, uid: str, poll_interval: float = 2.0, timeout: Optional[float] = None) -> StatusResponse:
        """
        Wait for a generation task to complete.

        Args:
            uid: The unique identifier of the generation task
            poll_interval: Time between status checks in seconds
            timeout: Maximum time to wait in seconds (None for no timeout)

        Returns:
            StatusResponse: Final status of the task

        Raises:
            Hunyuan3DAPIError: If the task fails or times out
        """
        start_time = time.time()

        while True:
            status_response = self.get_task_status(uid)

            if status_response.status == TaskStatus.COMPLETED:
                return status_response
            elif status_response.status == TaskStatus.ERROR:
                raise Hunyuan3DAPIError(
                    f"Task failed: {status_response.message}"
                )

            # Check timeout
            if timeout and (time.time() - start_time) > timeout:
                raise Hunyuan3DAPIError(
                    f"Task timed out after {timeout} seconds"
                )

            time.sleep(poll_interval)

    def generate_3d_model_async(self, request: GenerationRequest,
                               poll_interval: float = 2.0,
                               timeout: Optional[float] = None) -> bytes:
        """
        Generate a 3D model asynchronously and wait for completion.

        This is a convenience method that combines send_generation_task() and wait_for_completion().

        Args:
            request: GenerationRequest containing the image and generation parameters
            poll_interval: Time between status checks in seconds
            timeout: Maximum time to wait in seconds (None for no timeout)

        Returns:
            bytes: The generated 3D model file (GLB or OBJ format)

        Raises:
            Hunyuan3DAPIError: If the generation fails or times out
            Hunyuan3DAPIValidationError: If the request parameters are invalid
        """
        # Send the task
        response = self.send_generation_task(request)

        # Wait for completion
        status_response = self.wait_for_completion(
            response.uid, poll_interval, timeout
        )

        # Return the model data
        if status_response.model_base64:
            return base64.b64decode(status_response.model_base64)
        else:
            raise Hunyuan3DAPIError(
                "No model data received from completed task"
            )

    def save_model_to_file(self, model_data: bytes, file_path: str) -> None:
        """
        Save generated model data to a file.

        Args:
            model_data: The model data as bytes
            file_path: Path where to save the file
        """
        with open(file_path, 'wb') as f:
            f.write(model_data)

    def close(self) -> None:
        """Close the client session."""
        self.session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Convenience functions for common use cases
def generate_3d_model_from_image(image_path: str,
                                output_path: str,
                                base_url: str = "http://localhost:8081",
                                remove_background: bool = True,
                                texture: bool = False,
                                **kwargs) -> None:
    """
    Generate a 3D model from an image file and save it to disk.

    Args:
        image_path: Path to the input image file
        output_path: Path where to save the generated 3D model
        base_url: Base URL of the Hunyuan3D API server
        remove_background: Whether to automatically remove background
        texture: Whether to generate textures for the 3D model
        **kwargs: Additional generation parameters
    """
    with Hunyuan3DAPIClient(base_url) as client:
        # Create request from image file
        request = GenerationRequest.from_image_file(
            image_path,
            remove_background=remove_background,
            texture=texture,
            **kwargs
        )

        # Generate the model
        model_data = client.generate_3d_model_async(request)

        # Save to file
        client.save_model_to_file(model_data, output_path)
        print(f"3D model generated successfully and saved to: {output_path}")


def generate_3d_model_async_from_image(image_path: str,
                                      base_url: str = "http://localhost:8081",
                                      remove_background: bool = True,
                                      texture: bool = False,
                                      **kwargs) -> str:
    """
    Start an asynchronous 3D generation task and return the task ID.

    Args:
        image_path: Path to the input image file
        base_url: Base URL of the Hunyuan3D API server
        remove_background: Whether to automatically remove background
        texture: Whether to generate textures for the 3D model
        **kwargs: Additional generation parameters

    Returns:
        str: Task ID for tracking the generation progress
    """
    with Hunyuan3DAPIClient(base_url) as client:
        # Create request from image file
        request = GenerationRequest.from_image_file(
            image_path,
            remove_background=remove_background,
            texture=texture,
            **kwargs
        )

        # Send the task
        response = client.send_generation_task(request)
        return response.uid

def get_task_status(uid: str, base_url: str = "http://localhost:8081") -> StatusResponse:
    """
    Get the status of a generation task.
    """
    with Hunyuan3DAPIClient(base_url) as client:
        return client.get_task_status(uid)

def is_healthy(base_url: str = "http://localhost:8081") -> bool:
    """
    Get the health status of the Hunyuan3D API server.
    """
    try:
        with Hunyuan3DAPIClient(base_url) as client:
            return client.health_check().status == "healthy"
    except Exception as e:
        print(f"Error checking health: {e}")
    return False
