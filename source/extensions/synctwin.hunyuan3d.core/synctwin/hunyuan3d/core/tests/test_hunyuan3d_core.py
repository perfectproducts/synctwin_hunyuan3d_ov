# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

# NOTE:
#   omni.kit.test - std python's unittest module with additional wrapping to
#   add support for async/await tests
#   For most things refer to unittest docs:
#   https://docs.python.org/3/library/unittest.html
# Import extension python module we are testing with absolute import path,
# as if we are an external user (other extension)
import omni.kit.test
from omni.services.client import AsyncClient
import asyncio
import base64
import io
from PIL import Image
import aiohttp


# Having a test class derived from omni.kit.test.AsyncTestCase declared on
# the root of the module will make it auto-discoverable by omni.kit.test
class TestHunyuan3DServiceClient(omni.kit.test.AsyncTestCase):
    # Before running each test
    async def setUp(self):
        self.client = AsyncClient("http://192.168.178.147:8081")

    # After running each test
    async def tearDown(self):
        self.client.close()

    def create_test_image(self):
        img = Image.new('RGB', (256, 256), color='red')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return base64.b64encode(buffer.getvalue()).decode()

    async def test_serviceclient_generate(self):
        print("test_serviceclient_generate")
        sample_post_data = {
            "image": self.create_test_image()
        }

        # Since AsyncClient doesn't properly handle __raw__ for binary
        # responses, let's use the underlying HTTP client directly
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://192.168.178.147:8081/generate",
                json=sample_post_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                print(f"Response type: {type(response)}")
                print(f"Status: {response.status}")

                # Read the binary response directly
                try:
                    model_data = await response.read()
                    print(f"Received {len(model_data)} bytes of model data")
                    # You could save this to a file or process it further
                    # For testing purposes, just verify we got some data
                    self.assertGreater(len(model_data), 0)
                except Exception as e:
                    print(f"Error reading response: {e}")
                    # If the response is actually JSON (error response), try to
                    # parse it
                    try:
                        error_data = await response.json()
                        print(f"Error response: {error_data}")
                    except Exception as json_error:
                        print(f"Could not parse as JSON either: {json_error}")

    # Actual test, notice it is an "async" function, so "await" can be used
    # if needed
    async def test_serviceclient_health(self):
        v = await self.client.health()
        print(v)
        self.assertEqual(v["status"], "healthy")

    async def test_serviceclient_send(self):
        # Test image data (1x1 pixel PNG)
        test_image_data = (
            "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAYAAACp8Z5+AAAAD0lEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        )

        sample_post_data = {
            "image": test_image_data,
            "remove_background": True,
            "texture": False,
            "seed": 1234,
            "octree_resolution": 256,
            "num_inference_steps": 5,
            "guidance_scale": 5,
            "num_chunks": 8000,
            "face_count": 40000
        }
        # unpack the dictionary as parameters
        v = await self.client.send.post(**sample_post_data)
        uid = v['uid']
        num_retries = 0
        while True:
            v = await self.client.status(uid)
            print(v)
            if v['status'] == 'completed':
                break
            await asyncio.sleep(1)
            if num_retries > 10:
                break
            num_retries += 1
