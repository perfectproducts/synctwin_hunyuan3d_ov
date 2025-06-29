# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

# NOTE:
#   omni.kit.test - std python's unittest module with additional wrapping to add
#   suport for async/await tests
#   For most things refer to unittest docs:
#   https://docs.python.org/3/library/unittest.html
import omni.kit.test

import base64
import tempfile
import os
from unittest.mock import Mock, patch

# Import extension python module we are testing with absolute import path,
# as if we are external user (other extension)
from synctwin.hunyuan3d.tool import api_client


# Having a test class dervived from omni.kit.test.AsyncTestCase declared on the
# root of module will make it auto-discoverable by omni.kit.test
class TestApiClient(omni.kit.test.AsyncTestCase):
    # Before running each test
    async def setUp(self):
        pass

    # After running each test
    async def tearDown(self):
        pass

    # Test GenerationRequest creation with default values
    async def test_generation_request_defaults(self):
        # Pure base64 data (no data URL prefix)
        image_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        request = api_client.GenerationRequest(image=image_data)

        self.assertEqual(request.image, image_data)
        self.assertTrue(request.remove_background)
        self.assertFalse(request.texture)
        self.assertEqual(request.seed, 1234)
        self.assertEqual(request.octree_resolution, 256)
        self.assertEqual(request.num_inference_steps, 5)
        self.assertEqual(request.guidance_scale, 5.0)
        self.assertEqual(request.num_chunks, 8000)
        self.assertEqual(request.face_count, 40000)

    # Test GenerationRequest creation with custom values
    async def test_generation_request_custom_values(self):
        # Pure base64 data (no data URL prefix)
        image_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        request = api_client.GenerationRequest(
            image=image_data,
            remove_background=False,
            texture=True,
            seed=42,
            octree_resolution=128,
            num_inference_steps=10,
            guidance_scale=7.5,
            num_chunks=10000,
            face_count=50000
        )

        self.assertEqual(request.image, image_data)
        self.assertFalse(request.remove_background)
        self.assertTrue(request.texture)
        self.assertEqual(request.seed, 42)
        self.assertEqual(request.octree_resolution, 128)
        self.assertEqual(request.num_inference_steps, 10)
        self.assertEqual(request.guidance_scale, 7.5)
        self.assertEqual(request.num_chunks, 10000)
        self.assertEqual(request.face_count, 50000)

    # Test converting GenerationRequest to dictionary
    async def test_generation_request_to_dict(self):
        # Pure base64 data (no data URL prefix)
        image_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        request = api_client.GenerationRequest(
            image=image_data,
            remove_background=False,
            texture=True,
            seed=42
        )

        result = request.to_dict()

        self.assertEqual(result['image'], image_data)
        self.assertFalse(result['remove_background'])
        self.assertTrue(result['texture'])
        self.assertEqual(result['seed'], 42)
        self.assertEqual(result['octree_resolution'], 256)  # default value

    # Test creating GenerationRequest from image file
    async def test_generation_request_from_image_file(self):
        # Create a temporary image file
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            # Write a minimal PNG file
            png_data = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
            f.write(png_data)
            temp_file = f.name

        try:
            request = api_client.GenerationRequest.from_image_file(temp_file, seed=42)

            # The server expects pure base64 data, not data URL format
            self.assertTrue(request.image.startswith("iVBORw0KGgo"))
            self.assertEqual(request.seed, 42)
            self.assertTrue(request.remove_background)  # default value

        finally:
            os.unlink(temp_file)

    # Test HealthResponse creation
    async def test_health_response(self):
        health = api_client.HealthResponse(status="healthy", worker_id="worker-123")

        self.assertEqual(health.status, "healthy")
        self.assertEqual(health.worker_id, "worker-123")

    # Test GenerationResponse creation
    async def test_generation_response(self):
        response = api_client.GenerationResponse(uid="task-456")

        self.assertEqual(response.uid, "task-456")

    # Test StatusResponse with completed status
    async def test_status_response_completed(self):
        model_data = base64.b64encode(b"fake_model_data").decode('utf-8')
        status = api_client.StatusResponse(
            status="completed",
            model_base64=model_data,
            message=None
        )

        self.assertEqual(status.status, "completed")
        self.assertEqual(status.model_base64, model_data)
        self.assertIsNone(status.message)

    # Test StatusResponse with error status
    async def test_status_response_error(self):
        status = api_client.StatusResponse(
            status="error",
            model_base64=None,
            message="Something went wrong"
        )

        self.assertEqual(status.status, "error")
        self.assertIsNone(status.model_base64)
        self.assertEqual(status.message, "Something went wrong")

    # Test Hunyuan3DAPIClient health check
    @patch('requests.Session.request')
    async def test_client_health_check(self, mock_request):
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "healthy",
            "worker_id": "worker-123"
        }
        mock_request.return_value = mock_response

        client = api_client.Hunyuan3DAPIClient("http://localhost:8081")
        try:
            health = client.health_check()

            self.assertEqual(health.status, "healthy")
            self.assertEqual(health.worker_id, "worker-123")
            mock_request.assert_called_once()
        finally:
            client.close()

    # Test sending generation task
    @patch('requests.Session.request')
    async def test_send_generation_task(self, mock_request):
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"uid": "task-456"}
        mock_request.return_value = mock_response

        # Create request with pure base64 data
        image_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        request = api_client.GenerationRequest(image=image_data)

        client = api_client.Hunyuan3DAPIClient("http://localhost:8081")
        try:
            response = client.send_generation_task(request)

            self.assertEqual(response.uid, "task-456")
            mock_request.assert_called_once()
        finally:
            client.close()

    # Test getting task status
    @patch('requests.Session.request')
    async def test_get_task_status(self, mock_request):
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "completed",
            "model_base64": base64.b64encode(b"fake_model_data").decode('utf-8')
        }
        mock_request.return_value = mock_response

        client = api_client.Hunyuan3DAPIClient("http://localhost:8081")
        try:
            status = client.get_task_status("task-456")

            self.assertEqual(status.status, "completed")
            self.assertIsNotNone(status.model_base64)
            mock_request.assert_called_once()
        finally:
            client.close()

    # Test saving model to file
    async def test_save_model_to_file(self):
        model_data = b"fake_model_data"

        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_file = f.name

        try:
            client = api_client.Hunyuan3DAPIClient("http://localhost:8081")
            try:
                client.save_model_to_file(model_data, temp_file)

                with open(temp_file, 'rb') as f:
                    saved_data = f.read()

                self.assertEqual(saved_data, model_data)
            finally:
                client.close()
        finally:
            os.unlink(temp_file)

    # Test client as context manager
    async def test_context_manager(self):
        with api_client.Hunyuan3DAPIClient("http://localhost:8081") as client:
            self.assertIsInstance(client, api_client.Hunyuan3DAPIClient)

    # Test TaskStatus enum values
    async def test_task_status_enum(self):
        self.assertEqual(api_client.TaskStatus.PROCESSING, "processing")
        self.assertEqual(api_client.TaskStatus.COMPLETED, "completed")
        self.assertEqual(api_client.TaskStatus.ERROR, "error")
        self.assertEqual(api_client.TaskStatus.TEXTURING, "texturing")