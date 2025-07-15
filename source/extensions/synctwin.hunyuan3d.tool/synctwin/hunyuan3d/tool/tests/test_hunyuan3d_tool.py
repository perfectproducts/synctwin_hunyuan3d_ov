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
        pass