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
#   omni.kit.test - std python's unittest module with additional wrapping to add support for async/await tests
#   For most things refer to unittest docs: https://docs.python.org/3/library/unittest.html

import omni.kit.test
import asyncio
import threading
import tempfile
import os
import time
import base64
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from synctwin.hunyuan3d.core.client_manager import (
    Hunyuan3dClientManager,
    get_client_manager,
    TaskInfo,
    TaskState,
    _handle_usd_conversion_request
)
from synctwin.hunyuan3d.core.api_client import (
    StatusResponse,
    Hunyuan3DAPIError,
    Hunyuan3DAPIValidationError
)


class TestHunyuan3dClientManager(omni.kit.test.AsyncTestCase):
    """Test suite for Hunyuan3dClientManager."""
    
    async def setUp(self):
        """Set up test fixtures before each test method."""
        # Reset singleton instance before each test
        Hunyuan3dClientManager._instance = None
        
        # Create a fresh client manager for each test
        self.client_manager = Hunyuan3dClientManager()
        
        # Mock paths and files
        self.temp_dir = tempfile.mkdtemp()
        self.test_image_path = os.path.join(self.temp_dir, "test_image.jpg")
        self.test_usd_path = os.path.join(self.temp_dir, "test_output.usd")
        
        # Create test image file
        with open(self.test_image_path, "wb") as f:
            f.write(b"fake_image_data")
        
        # Mock callbacks
        self.progress_callback = Mock()
        self.completion_callback = Mock()
        
        # Test task parameters
        self.test_generation_params = {
            "seed": 42,
            "texture": True,
            "remove_background": False
        }
    
    async def tearDown(self):
        """Clean up after each test method."""
        # Shutdown client manager
        if hasattr(self, 'client_manager'):
            try:
                self.client_manager.shutdown()
            except Exception as e:
                print(f"Warning: Failed to shutdown client manager: {e}")
        
        # Clean up temp files
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        
        # Reset singleton
        Hunyuan3dClientManager._instance = None
    
    async def test_singleton_pattern(self):
        """Test that client manager follows singleton pattern."""
        manager1 = Hunyuan3dClientManager()
        manager2 = Hunyuan3dClientManager()
        manager3 = get_client_manager()
        
        self.assertIs(manager1, manager2)
        self.assertIs(manager2, manager3)
        self.assertIs(manager1, self.client_manager)
    
    async def test_set_default_base_url(self):
        """Test setting default base URL."""
        test_url = "http://test-server:8080"
        self.client_manager.set_default_base_url(test_url)
        self.assertEqual(self.client_manager._default_base_url, test_url)
    
    async def test_set_poll_interval(self):
        """Test setting poll interval."""
        test_interval = 5.0
        self.client_manager.set_poll_interval(test_interval)
        self.assertEqual(self.client_manager._poll_interval, test_interval)
    
    @patch('synctwin.hunyuan3d.core.client_manager.Hunyuan3DAPIClient')
    async def test_submit_task_success(self, mock_api_client):
        """Test successful task submission."""
        # Mock API client response
        mock_client_instance = Mock()
        mock_client_instance.__enter__ = Mock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = Mock(return_value=None)
        mock_api_client.return_value = mock_client_instance
        
        mock_response = Mock()
        mock_response.uid = "test-task-123"
        mock_client_instance.send_generation_task.return_value = mock_response
        
        # Submit task
        task_uid = self.client_manager.submit_task(
            image_path=self.test_image_path,
            output_usd_path=self.test_usd_path,
            generation_params=self.test_generation_params,
            progress_callback=self.progress_callback,
            completion_callback=self.completion_callback
        )
        
        # Verify task was submitted
        self.assertEqual(task_uid, "test-task-123")
        self.assertIn(task_uid, self.client_manager._tasks)
        self.assertIn(task_uid, self.client_manager._active_tasks)
        
        # Verify task info
        task_info = self.client_manager.get_task_info(task_uid)
        self.assertIsNotNone(task_info)
        self.assertEqual(task_info.task_uid, task_uid)
        self.assertEqual(task_info.image_path, self.test_image_path)
        self.assertEqual(task_info.output_usd_path, self.test_usd_path)
        self.assertEqual(task_info.state, TaskState.PENDING)
        
        # Verify callbacks were called
        self.progress_callback.assert_called_once_with(task_uid, "Generation started")
    
    @patch('synctwin.hunyuan3d.core.client_manager.Hunyuan3DAPIClient')
    async def test_submit_task_api_error(self, mock_api_client):
        """Test task submission with API error."""
        # Mock API client to raise error
        mock_client_instance = Mock()
        mock_client_instance.__enter__ = Mock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = Mock(return_value=None)
        mock_api_client.return_value = mock_client_instance
        
        mock_client_instance.send_generation_task.side_effect = Hunyuan3DAPIError("API Error")
        
        # Test that exception is propagated
        with self.assertRaises(Hunyuan3DAPIError):
            self.client_manager.submit_task(
                image_path=self.test_image_path,
                output_usd_path=self.test_usd_path,
                generation_params=self.test_generation_params
            )
    
    async def test_cancel_task(self):
        """Test task cancellation."""
        # Add a mock task
        task_uid = "test-task-123"
        task_info = TaskInfo(
            task_uid=task_uid,
            image_path=self.test_image_path,
            output_usd_path=self.test_usd_path,
            base_url="http://localhost:8081",
            generation_params=self.test_generation_params,
            temp_dir=tempfile.mkdtemp()
        )
        
        self.client_manager._tasks[task_uid] = task_info
        self.client_manager._active_tasks.add(task_uid)
        
        # Cancel task
        result = self.client_manager.cancel_task(task_uid)
        
        # Verify cancellation
        self.assertTrue(result)
        self.assertNotIn(task_uid, self.client_manager._active_tasks)
        self.assertIn(task_uid, self.client_manager._tasks)  # Task info kept for reference
    
    async def test_cancel_nonexistent_task(self):
        """Test cancelling non-existent task."""
        result = self.client_manager.cancel_task("non-existent-task")
        self.assertFalse(result)
    
    @patch('synctwin.hunyuan3d.core.client_manager.Hunyuan3DAPIClient')
    async def test_check_task_status_completed(self, mock_api_client):
        """Test checking task status for completed task."""
        # Set up mock task
        task_uid = "test-task-123"
        task_info = TaskInfo(
            task_uid=task_uid,
            image_path=self.test_image_path,
            output_usd_path=self.test_usd_path,
            base_url="http://localhost:8081",
            generation_params=self.test_generation_params,
            temp_dir=tempfile.mkdtemp(),
            progress_callback=self.progress_callback,
            completion_callback=self.completion_callback
        )
        
        self.client_manager._tasks[task_uid] = task_info
        self.client_manager._active_tasks.add(task_uid)
        
        # Mock API client response
        mock_client_instance = Mock()
        mock_client_instance.__enter__ = Mock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = Mock(return_value=None)
        mock_api_client.return_value = mock_client_instance
        
        # Mock completed status with model data
        mock_model_data = b"fake_glb_data"
        mock_base64_data = base64.b64encode(mock_model_data).decode('utf-8')
        
        mock_status_response = StatusResponse(
            status="completed",
            model_base64=mock_base64_data,
            message="Generation completed"
        )
        mock_client_instance.get_task_status.return_value = mock_status_response
        
        # Mock omni.kit.app.queue_event
        with patch('omni.kit.app.queue_event') as mock_queue_event:
            # Check task status
            self.client_manager._check_task_status(task_uid)
            
            # Verify GLB file was created
            self.assertIsNotNone(task_info.glb_path)
            self.assertTrue(os.path.exists(task_info.glb_path))
            
            # Verify GLB file content
            with open(task_info.glb_path, "rb") as f:
                saved_data = f.read()
            self.assertEqual(saved_data, mock_model_data)
            
            # Verify state update
            self.assertEqual(task_info.state, TaskState.CONVERTING)
            
            # Verify conversion event was queued
            mock_queue_event.assert_called_once_with(
                "hunyuan3d_start_conversion",
                payload={
                    "task_uid": task_uid,
                    "glb_path": task_info.glb_path,
                    "usd_path": task_info.output_usd_path
                }
            )
            
            # Verify progress callback
            self.progress_callback.assert_called_with(task_uid, "Converting to USD...")
    
    @patch('synctwin.hunyuan3d.core.client_manager.Hunyuan3DAPIClient')
    async def test_check_task_status_failed(self, mock_api_client):
        """Test checking task status for failed task."""
        # Set up mock task
        task_uid = "test-task-123"
        task_info = TaskInfo(
            task_uid=task_uid,
            image_path=self.test_image_path,
            output_usd_path=self.test_usd_path,
            base_url="http://localhost:8081",
            generation_params=self.test_generation_params,
            temp_dir=tempfile.mkdtemp(),
            progress_callback=self.progress_callback,
            completion_callback=self.completion_callback
        )
        
        self.client_manager._tasks[task_uid] = task_info
        self.client_manager._active_tasks.add(task_uid)
        
        # Mock API client response
        mock_client_instance = Mock()
        mock_client_instance.__enter__ = Mock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = Mock(return_value=None)
        mock_api_client.return_value = mock_client_instance
        
        # Mock failed status
        mock_status_response = StatusResponse(
            status="error",
            message="Generation failed"
        )
        mock_client_instance.get_task_status.return_value = mock_status_response
        
        # Check task status
        self.client_manager._check_task_status(task_uid)
        
        # Verify state update
        self.assertEqual(task_info.state, TaskState.FAILED)
        self.assertNotIn(task_uid, self.client_manager._active_tasks)
        
        # Verify callbacks
        self.progress_callback.assert_called_with(task_uid, "Failed: Generation failed")
        self.completion_callback.assert_called_with(task_uid, False, "Generation failed")
    
    async def test_handle_conversion_completed_success(self):
        """Test handling successful USD conversion."""
        # Set up mock task
        task_uid = "test-task-123"
        task_info = TaskInfo(
            task_uid=task_uid,
            image_path=self.test_image_path,
            output_usd_path=self.test_usd_path,
            base_url="http://localhost:8081",
            generation_params=self.test_generation_params,
            temp_dir=tempfile.mkdtemp(),
            progress_callback=self.progress_callback,
            completion_callback=self.completion_callback
        )
        
        self.client_manager._tasks[task_uid] = task_info
        self.client_manager._active_tasks.add(task_uid)
        
        # Handle conversion completion
        self.client_manager._handle_conversion_completed(task_uid, True, self.test_usd_path)
        
        # Verify state update
        self.assertEqual(task_info.state, TaskState.COMPLETED)
        self.assertNotIn(task_uid, self.client_manager._active_tasks)
        
        # Verify callbacks
        self.progress_callback.assert_called_with(task_uid, "USD conversion completed")
        self.completion_callback.assert_called_with(task_uid, True, self.test_usd_path)
    
    async def test_handle_conversion_completed_failure(self):
        """Test handling failed USD conversion."""
        # Set up mock task
        task_uid = "test-task-123"
        task_info = TaskInfo(
            task_uid=task_uid,
            image_path=self.test_image_path,
            output_usd_path=self.test_usd_path,
            base_url="http://localhost:8081",
            generation_params=self.test_generation_params,
            temp_dir=tempfile.mkdtemp(),
            progress_callback=self.progress_callback,
            completion_callback=self.completion_callback
        )
        
        self.client_manager._tasks[task_uid] = task_info
        self.client_manager._active_tasks.add(task_uid)
        
        error_message = "USD conversion failed"
        
        # Handle conversion completion
        self.client_manager._handle_conversion_completed(task_uid, False, error_message)
        
        # Verify state update
        self.assertEqual(task_info.state, TaskState.FAILED)
        self.assertNotIn(task_uid, self.client_manager._active_tasks)
        
        # Verify callbacks
        self.progress_callback.assert_called_with(task_uid, f"USD conversion failed: {error_message}")
        self.completion_callback.assert_called_with(task_uid, False, error_message)
    
    @patch('carb.eventdispatcher.get_eventdispatcher')
    async def test_subscribe_to_conversion_events(self, mock_get_dispatcher):
        """Test subscribing to conversion events."""
        # Mock event dispatcher
        mock_dispatcher = Mock()
        mock_subscription = Mock()
        mock_get_dispatcher.return_value = mock_dispatcher
        mock_dispatcher.observe_event.return_value = mock_subscription
        
        # Subscribe to events
        self.client_manager.subscribe_to_conversion_events()
        
        # Verify subscription
        mock_dispatcher.observe_event.assert_called_once_with(
            observer_name="Hunyuan3D Client Manager",
            event_name="hunyuan3d_start_conversion",
            on_event=_handle_usd_conversion_request
        )
        
        self.assertEqual(self.client_manager._conversion_subscription, mock_subscription)
    
    @patch('carb.eventdispatcher.get_eventdispatcher')
    async def test_subscribe_to_conversion_events_already_subscribed(self, mock_get_dispatcher):
        """Test subscribing to conversion events when already subscribed."""
        # Mock event dispatcher
        mock_dispatcher = Mock()
        mock_subscription = Mock()
        mock_get_dispatcher.return_value = mock_dispatcher
        mock_dispatcher.observe_event.return_value = mock_subscription
        
        # Set up existing subscription
        self.client_manager._conversion_subscription = mock_subscription
        
        # Try to subscribe again
        self.client_manager.subscribe_to_conversion_events()
        
        # Verify no new subscription was created
        mock_dispatcher.observe_event.assert_not_called()
    
    @patch('carb.eventdispatcher.get_eventdispatcher')
    async def test_shutdown_with_event_subscription(self, mock_get_dispatcher):
        """Test shutdown with active event subscription."""
        # Mock event dispatcher
        mock_dispatcher = Mock()
        mock_subscription = Mock()
        mock_get_dispatcher.return_value = mock_dispatcher
        
        # Set up existing subscription
        self.client_manager._conversion_subscription = mock_subscription
        
        # Shutdown
        self.client_manager.shutdown()
        
        # Verify unsubscription (try both possible methods)
        try:
            mock_dispatcher.unsubscribe.assert_called_once_with(mock_subscription)
        except AttributeError:
            mock_dispatcher.unsubscribe_event.assert_called_once_with(mock_subscription)
        
        self.assertIsNone(self.client_manager._conversion_subscription)
    
    async def test_cleanup_completed_task(self):
        """Test cleaning up completed task resources."""
        # Create temp files
        temp_dir = tempfile.mkdtemp()
        glb_path = os.path.join(temp_dir, "test.glb")
        
        with open(glb_path, "wb") as f:
            f.write(b"fake_glb_data")
        
        # Set up mock task
        task_uid = "test-task-123"
        task_info = TaskInfo(
            task_uid=task_uid,
            image_path=self.test_image_path,
            output_usd_path=self.test_usd_path,
            base_url="http://localhost:8081",
            generation_params=self.test_generation_params,
            temp_dir=temp_dir,
            glb_path=glb_path
        )
        
        self.client_manager._tasks[task_uid] = task_info
        
        # Verify files exist before cleanup
        self.assertTrue(os.path.exists(glb_path))
        self.assertTrue(os.path.exists(temp_dir))
        
        # Clean up task
        self.client_manager.cleanup_completed_task(task_uid)
        
        # Verify files are removed
        self.assertFalse(os.path.exists(glb_path))
        self.assertFalse(os.path.exists(temp_dir))
    
    async def test_polling_thread_starts(self):
        """Test that polling thread starts on initialization."""
        # Verify polling thread is running
        self.assertIsNotNone(self.client_manager._polling_thread)
        self.assertTrue(self.client_manager._polling_thread.is_alive())
        self.assertFalse(self.client_manager._stop_polling)
    
    async def test_polling_thread_stops_on_shutdown(self):
        """Test that polling thread stops on shutdown."""
        # Get reference to thread
        polling_thread = self.client_manager._polling_thread
        
        # Shutdown
        self.client_manager.shutdown()
        
        # Wait a bit for thread to stop
        await asyncio.sleep(0.1)
        
        # Verify thread stopped
        self.assertTrue(self.client_manager._stop_polling)
        self.assertFalse(polling_thread.is_alive())


class TestUsdConversionHandler(omni.kit.test.AsyncTestCase):
    """Test suite for USD conversion event handler."""
    
    async def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.glb_path = os.path.join(self.temp_dir, "test.glb")
        self.usd_path = os.path.join(self.temp_dir, "test.usd")
        self.task_uid = "test-task-123"
        
        # Create test GLB file
        with open(self.glb_path, "wb") as f:
            f.write(b"fake_glb_data")
    
    async def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @patch('omni.kit.asset_converter.get_instance')
    @patch('synctwin.hunyuan3d.core.client_manager.get_client_manager')
    @patch('asyncio.ensure_future')
    async def test_handle_usd_conversion_request(self, mock_ensure_future, mock_get_client_manager, mock_get_converter):
        """Test handling USD conversion request event."""
        # Mock client manager
        mock_client_manager = Mock()
        mock_get_client_manager.return_value = mock_client_manager
        
        # Mock converter
        mock_converter = Mock()
        mock_task = Mock()
        mock_get_converter.return_value = mock_converter
        mock_converter.create_converter_task.return_value = mock_task
        
        # Create event payload
        event = {
            "task_uid": self.task_uid,
            "glb_path": self.glb_path,
            "usd_path": self.usd_path
        }
        
        # Handle conversion request
        _handle_usd_conversion_request(event)
        
        # Verify asyncio.ensure_future was called
        mock_ensure_future.assert_called_once()
        
        # Get the coroutine that was passed to ensure_future
        coro = mock_ensure_future.call_args[0][0]
        self.assertTrue(asyncio.iscoroutine(coro))
        
        # Clean up the coroutine
        coro.close()
    
    async def test_handle_usd_conversion_request_missing_params(self):
        """Test handling USD conversion request with missing parameters."""
        # Create incomplete event payload
        event = {
            "task_uid": self.task_uid,
            "glb_path": self.glb_path
            # Missing usd_path
        }
        
        # Handle conversion request (should do nothing)
        with patch('asyncio.ensure_future') as mock_ensure_future:
            _handle_usd_conversion_request(event)
            
            # Verify no coroutine was created
            mock_ensure_future.assert_not_called()