# Hunyuan3D API Client

A Python client for the Hunyuan3D 2.1 API server that provides endpoints for generating 3D models from 2D images.

## Features

- **3D Shape Generation**: Convert 2D images to 3D meshes
- **Texture Generation**: Generate PBR textures for 3D models
- **Background Removal**: Automatic background removal from input images
- **Multiple Formats**: Support for GLB and OBJ output formats
- **Async Processing**: Background task processing with status tracking
- **Error Handling**: Comprehensive error handling with custom exceptions
- **Type Safety**: Full type hints and dataclass models
- **Context Manager**: Safe resource management with context managers

## Installation

### Prerequisites

- Python 3.7 or higher
- Hunyuan3D API server running (typically on `http://localhost:8000`)

### Dependencies

```bash
pip install requests
```

## Quick Start

### Basic Usage

```python
from api_client import generate_3d_model_from_image

# Generate a 3D model from an image
generate_3d_model_from_image(
    image_path="path/to/your/image.png",
    output_path="output_model.glb",
    remove_background=True,
    texture=True
)
```

### Using the Client Directly

```python
from api_client import Hunyuan3DAPIClient, GenerationRequest

with Hunyuan3DAPIClient("http://localhost:8000") as client:
    # Check server health
    health = client.health_check()
    print(f"Server status: {health.status}")

    # Create request from image file
    request = GenerationRequest.from_image_file(
        "path/to/your/image.png",
        remove_background=True,
        texture=True,
        seed=123
    )

    # Generate 3D model
    model_data = client.generate_3d_model_async(request)

    # Save the model
    client.save_model_to_file(model_data, "output_model.glb")
```

## API Reference

### Hunyuan3DAPIClient

The main client class for interacting with the Hunyuan3D API.

#### Constructor

```python
Hunyuan3DAPIClient(base_url: str = "http://localhost:8000", timeout: int = 30)
```

- `base_url`: Base URL of the Hunyuan3D API server
- `timeout`: Request timeout in seconds

#### Methods

##### health_check() -> HealthResponse

Check the health status of the Hunyuan3D API server.

```python
health = client.health_check()
print(f"Status: {health.status}, Worker ID: {health.worker_id}")
```

##### generate_3d_model(request: GenerationRequest) -> bytes

Generate a 3D model from an input image synchronously.

```python
request = GenerationRequest.from_image_file("image.png")
model_data = client.generate_3d_model(request)
```

##### send_generation_task(request: GenerationRequest) -> GenerationResponse

Send a 3D generation task to be processed asynchronously.

```python
request = GenerationRequest.from_image_file("image.png")
response = client.send_generation_task(request)
task_id = response.uid
```

##### get_task_status(uid: str) -> StatusResponse

Check the status of a generation task.

```python
status = client.get_task_status(task_id)
print(f"Status: {status.status}")
```

##### wait_for_completion(uid: str, poll_interval: float = 2.0, timeout: Optional[float] = None) -> StatusResponse

Wait for a generation task to complete.

```python
status = client.wait_for_completion(task_id, timeout=300)
if status.model_base64:
    model_data = base64.b64decode(status.model_base64)
```

##### generate_3d_model_async(request: GenerationRequest, poll_interval: float = 2.0, timeout: Optional[float] = None) -> bytes

Generate a 3D model asynchronously and wait for completion.

```python
request = GenerationRequest.from_image_file("image.png")
model_data = client.generate_3d_model_async(request, timeout=300)
```

##### save_model_to_file(model_data: bytes, file_path: str) -> None

Save generated model data to a file.

```python
client.save_model_to_file(model_data, "output.glb")
```

### GenerationRequest

Request model for 3D generation API.

#### Constructor

```python
GenerationRequest(
    image: str,  # Base64 encoded input image
    remove_background: bool = True,
    texture: bool = False,
    seed: int = 1234,
    octree_resolution: int = 256,
    num_inference_steps: int = 5,
    guidance_scale: float = 5.0,
    num_chunks: int = 8000,
    face_count: int = 40000
)
```

#### Class Methods

##### from_image_file(image_path: str, **kwargs) -> GenerationRequest

Create a GenerationRequest from an image file.

```python
request = GenerationRequest.from_image_file(
    "image.png",
    remove_background=True,
    texture=True,
    seed=42
)
```

### Response Models

#### HealthResponse

```python
@dataclass
class HealthResponse:
    status: str
    worker_id: str
```

#### GenerationResponse

```python
@dataclass
class GenerationResponse:
    uid: str
```

#### StatusResponse

```python
@dataclass
class StatusResponse:
    status: str
    model_base64: Optional[str] = None
    message: Optional[str] = None
```

### Task Status Enum

```python
class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"
```

## Error Handling

The client provides custom exceptions for different error scenarios:

### Hunyuan3DAPIError

Base exception for Hunyuan3D API errors.

### Hunyuan3DAPIValidationError

Exception raised for validation errors.

```python
try:
    client.generate_3d_model(request)
except Hunyuan3DAPIValidationError as e:
    print(f"Validation errors: {e.validation_errors}")
except Hunyuan3DAPIError as e:
    print(f"API error: {e}")
```

## Usage Examples

### Example 1: Simple Generation

```python
from api_client import generate_3d_model_from_image

generate_3d_model_from_image(
    image_path="input.png",
    output_path="output.glb",
    remove_background=True,
    texture=True
)
```

### Example 2: Async Task Tracking

```python
from api_client import Hunyuan3DAPIClient, GenerationRequest

with Hunyuan3DAPIClient() as client:
    # Submit task
    request = GenerationRequest.from_image_file("input.png")
    response = client.send_generation_task(request)
    task_id = response.uid

    # Monitor progress
    while True:
        status = client.get_task_status(task_id)
        print(f"Status: {status.status}")

        if status.status == "completed":
            if status.model_base64:
                model_data = base64.b64decode(status.model_base64)
                client.save_model_to_file(model_data, "output.glb")
            break
        elif status.status == "error":
            print(f"Error: {status.message}")
            break

        time.sleep(2)
```

### Example 3: Batch Processing

```python
import os
from api_client import Hunyuan3DAPIClient, GenerationRequest

image_directory = "images"
output_directory = "models"
os.makedirs(output_directory, exist_ok=True)

with Hunyuan3DAPIClient() as client:
    for image_file in os.listdir(image_directory):
        if image_file.lower().endswith(('.png', '.jpg', '.jpeg')):
            image_path = os.path.join(image_directory, image_file)
            output_path = os.path.join(output_directory, f"{image_file}.glb")

            request = GenerationRequest.from_image_file(image_path)
            model_data = client.generate_3d_model_async(request)
            client.save_model_to_file(model_data, output_path)
```

## Configuration Options

### Generation Parameters

- `remove_background`: Whether to automatically remove background (default: True)
- `texture`: Whether to generate textures for the 3D model (default: False)
- `seed`: Random seed for reproducible generation (default: 1234)
- `octree_resolution`: Resolution of the octree for mesh generation (64-512, default: 256)
- `num_inference_steps`: Number of inference steps for generation (1-20, default: 5)
- `guidance_scale`: Guidance scale for generation (0.1-20.0, default: 5.0)
- `num_chunks`: Number of chunks for processing (1000-20000, default: 8000)
- `face_count`: Maximum number of faces for texture generation (1000-100000, default: 40000)

### Client Configuration

- `base_url`: API server URL (default: "http://localhost:8000")
- `timeout`: Request timeout in seconds (default: 30)
- `poll_interval`: Time between status checks for async operations (default: 2.0)

## Model Information

- **Model**: Hunyuan3D-2.1 by Tencent
- **License**: TENCENT HUNYUAN NON-COMMERCIAL LICENSE AGREEMENT
- **Capabilities**: Image-to-3D, Texture Generation
- **Output Formats**: GLB, OBJ

## Troubleshooting

### Common Issues

1. **Connection Error**: Make sure the Hunyuan3D API server is running
2. **Timeout Error**: Increase the timeout parameter for long-running operations
3. **Validation Error**: Check that the image format is supported and the parameters are within valid ranges
4. **Task Failed**: Check the error message in the status response for details

### Debug Mode

Enable debug logging to see detailed request/response information:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## License

This client is provided under the same license as the Hunyuan3D model:
TENCENT HUNYUAN NON-COMMERCIAL LICENSE AGREEMENT

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Support

For issues and questions:
- Check the troubleshooting section
- Review the API documentation
- Open an issue on the repository