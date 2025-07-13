# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""
Hunyuan3D Client Manager

Singleton client manager that handles all Hunyuan3D API requests and task management.
"""

import threading
import time
import tempfile
import base64
import asyncio
from typing import Optional, Dict, Any, Callable, Set
from dataclasses import dataclass
from enum import Enum
import omni.kit.asset_converter as converter
import omni.kit.app
from .api_client import (
    Hunyuan3DAPIClient, 
    GenerationRequest, 
    Hunyuan3DAPIError,
    Hunyuan3DAPIValidationError,
    StatusResponse
)


class TaskState(str, Enum):
    """Task states managed by the client."""
    PENDING = "pending"
    PROCESSING = "processing"
    TEXTURING = "texturing"
    CONVERTING = "converting"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskInfo:
    """Information about a generation task."""
    task_uid: str
    image_path: str
    output_usd_path: str
    base_url: str
    generation_params: Dict[str, Any]
    progress_callback: Optional[Callable[[str, str], None]] = None  # (task_uid, message)
    completion_callback: Optional[Callable[[str, bool, str], None]] = None  # (task_uid, success, path_or_error)
    state: TaskState = TaskState.PENDING
    glb_path: Optional[str] = None
    temp_dir: Optional[str] = None


class Hunyuan3dClientManager:
    """
    Singleton client manager for Hunyuan3D operations.
    
    This manager handles:
    - API client connections
    - Task lifecycle management
    - Status polling in background thread
    - GLB to USD conversion
    - Progress reporting and callbacks
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self._tasks: Dict[str, TaskInfo] = {}
        self._active_tasks: Set[str] = set()
        self._polling_thread = None
        self._stop_polling = False
        self._poll_interval = 2.0
        self._default_base_url = "http://localhost:8081"
        
        # Start the polling thread
        self._start_polling_thread()
    
    def set_default_base_url(self, base_url: str):
        """Set the default base URL for API requests."""
        self._default_base_url = base_url
    
    def set_poll_interval(self, interval: float):
        """Set the polling interval in seconds."""
        self._poll_interval = interval
    
    def submit_task(
        self,
        image_path: str,
        output_usd_path: str,
        generation_params: Dict[str, Any],
        base_url: Optional[str] = None,
        progress_callback: Optional[Callable[[str, str], None]] = None,
        completion_callback: Optional[Callable[[str, bool, str], None]] = None
    ) -> str:
        """
        Submit a new image-to-USD generation task.
        
        Args:
            image_path: Path to input image
            output_usd_path: Path for output USD file
            generation_params: Parameters for generation (seed, texture, etc.)
            base_url: API base URL (uses default if None)
            progress_callback: Callback for progress updates (task_uid, message)
            completion_callback: Callback for completion (task_uid, success, path_or_error)
            
        Returns:
            Task UID for tracking
            
        Raises:
            Hunyuan3DAPIError: If API request fails
        """
        if base_url is None:
            base_url = self._default_base_url
        
        # Create generation request
        request = GenerationRequest.from_image_file(image_path, **generation_params)
        
        # Submit to API
        with Hunyuan3DAPIClient(base_url) as client:
            response = client.send_generation_task(request)
            task_uid = response.uid
        
        # Create temp directory for this task
        temp_dir = tempfile.mkdtemp()
        
        # Store task info
        task_info = TaskInfo(
            task_uid=task_uid,
            image_path=image_path,
            output_usd_path=output_usd_path,
            base_url=base_url,
            generation_params=generation_params,
            progress_callback=progress_callback,
            completion_callback=completion_callback,
            temp_dir=temp_dir
        )
        
        with self._lock:
            self._tasks[task_uid] = task_info
            self._active_tasks.add(task_uid)
        
        if progress_callback:
            progress_callback(task_uid, "Generation started")
        
        print(f"[Hunyuan3dClientManager] Submitted task {task_uid}")
        return task_uid
    
    def get_task_info(self, task_uid: str) -> Optional[TaskInfo]:
        """Get information about a task."""
        with self._lock:
            return self._tasks.get(task_uid)
    
    def cancel_task(self, task_uid: str) -> bool:
        """
        Cancel a task (removes from tracking, but server-side task may continue).
        
        Args:
            task_uid: Task to cancel
            
        Returns:
            True if task was found and cancelled
        """
        with self._lock:
            if task_uid in self._tasks:
                task_info = self._tasks[task_uid]
                self._active_tasks.discard(task_uid)
                
                # Clean up temp directory
                self._cleanup_task_files(task_info)
                
                print(f"[Hunyuan3dClientManager] Cancelled task {task_uid}")
                return True
        return False
    
    def cleanup_completed_task(self, task_uid: str):
        """Clean up a completed task's resources."""
        with self._lock:
            if task_uid in self._tasks:
                task_info = self._tasks[task_uid]
                self._cleanup_task_files(task_info)
                print(f"[Hunyuan3dClientManager] Cleaned up completed task {task_uid}")
    
    def _cleanup_task_files(self, task_info: TaskInfo):
        """Clean up temporary files for a task."""
        import os
        import shutil
        
        # Remove GLB file
        if task_info.glb_path and os.path.exists(task_info.glb_path):
            try:
                os.remove(task_info.glb_path)
            except Exception as e:
                print(f"[Hunyuan3dClientManager] Failed to remove GLB: {e}")
        
        # Remove temp directory
        if task_info.temp_dir and os.path.exists(task_info.temp_dir):
            try:
                shutil.rmtree(task_info.temp_dir)
            except Exception as e:
                print(f"[Hunyuan3dClientManager] Failed to remove temp dir: {e}")
    
    def _start_polling_thread(self):
        """Start the background polling thread."""
        self._stop_polling = False
        self._polling_thread = threading.Thread(target=self._polling_loop, daemon=True)
        self._polling_thread.start()
        print("[Hunyuan3dClientManager] Started polling thread")
    
    def _polling_loop(self):
        """Main polling loop that runs in background thread."""
        while not self._stop_polling:
            # Get snapshot of active tasks
            with self._lock:
                active_task_uids = list(self._active_tasks)
            
            if not active_task_uids:
                time.sleep(self._poll_interval)
                continue
            
            # Check each active task
            for task_uid in active_task_uids:
                try:
                    self._check_task_status(task_uid)
                except Exception as e:
                    print(f"[Hunyuan3dClientManager] Error checking task {task_uid}: {e}")
            
            time.sleep(self._poll_interval)
        
        print("[Hunyuan3dClientManager] Polling thread stopped")
    
    def _check_task_status(self, task_uid: str):
        """Check status of a single task."""
        with self._lock:
            task_info = self._tasks.get(task_uid)
        
        if not task_info or task_uid not in self._active_tasks:
            return
        
        try:
            # Check API status
            with Hunyuan3DAPIClient(task_info.base_url) as client:
                status_response = client.get_task_status(task_uid)
            
            # Update task state
            if status_response.status == "completed":
                self._handle_generation_completed(task_uid, task_info, status_response)
            elif status_response.status == "error":
                self._handle_generation_failed(task_uid, task_info, status_response.message or "Unknown error")
            else:
                # Still processing
                if task_info.progress_callback:
                    task_info.progress_callback(task_uid, f"Status: {status_response.status}")
        
        except Exception as e:
            self._handle_generation_failed(task_uid, task_info, f"Status check failed: {str(e)}")
    
    def _handle_generation_completed(self, task_uid: str, task_info: TaskInfo, status_response: StatusResponse):
        """Handle completed generation."""
        print(f"[Hunyuan3dClientManager] Generation completed for task {task_uid}")
        
        if not status_response.model_base64:
            self._handle_generation_failed(task_uid, task_info, "No model data received")
            return
        
        try:
            # Save GLB file
            model_data = base64.b64decode(status_response.model_base64)
            glb_path = f"{task_info.temp_dir}/{task_uid}.glb"
            
            with open(glb_path, "wb") as f:
                f.write(model_data)
            
            task_info.glb_path = glb_path
            task_info.state = TaskState.CONVERTING
            
            if task_info.progress_callback:
                task_info.progress_callback(task_uid, "Converting to USD...")
            
            # Start USD conversion on main thread
            omni.kit.app.queue_event(
                "hunyuan3d_start_conversion",
                payload={
                    "task_uid": task_uid,
                    "glb_path": glb_path,
                    "usd_path": task_info.output_usd_path
                }
            )
            
        except Exception as e:
            self._handle_generation_failed(task_uid, task_info, f"Failed to process GLB: {str(e)}")
    
    def _handle_generation_failed(self, task_uid: str, task_info: TaskInfo, error_message: str):
        """Handle generation failure."""
        print(f"[Hunyuan3dClientManager] Generation failed for task {task_uid}: {error_message}")
        
        with self._lock:
            self._active_tasks.discard(task_uid)
            task_info.state = TaskState.FAILED
        
        if task_info.progress_callback:
            task_info.progress_callback(task_uid, f"Failed: {error_message}")
        
        if task_info.completion_callback:
            task_info.completion_callback(task_uid, False, error_message)
    
    def _handle_conversion_completed(self, task_uid: str, success: bool, result_path_or_error: str):
        """Handle USD conversion completion."""
        with self._lock:
            task_info = self._tasks.get(task_uid)
            if task_info:
                self._active_tasks.discard(task_uid)
                task_info.state = TaskState.COMPLETED if success else TaskState.FAILED
        
        if not task_info:
            return
        
        if success:
            print(f"[Hunyuan3dClientManager] USD conversion completed for task {task_uid}: {result_path_or_error}")
            if task_info.progress_callback:
                task_info.progress_callback(task_uid, "USD conversion completed")
        else:
            print(f"[Hunyuan3dClientManager] USD conversion failed for task {task_uid}: {result_path_or_error}")
            if task_info.progress_callback:
                task_info.progress_callback(task_uid, f"USD conversion failed: {result_path_or_error}")
        
        if task_info.completion_callback:
            task_info.completion_callback(task_uid, success, result_path_or_error)
    
    def shutdown(self):
        """Shutdown the client manager."""
        print("[Hunyuan3dClientManager] Shutting down...")
        
        # Stop polling
        self._stop_polling = True
        if self._polling_thread and self._polling_thread.is_alive():
            self._polling_thread.join(timeout=2.0)
        
        # Clean up all tasks
        with self._lock:
            for task_info in self._tasks.values():
                self._cleanup_task_files(task_info)
            self._tasks.clear()
            self._active_tasks.clear()
        
        print("[Hunyuan3dClientManager] Shutdown complete")


# Global singleton instance
def get_client_manager() -> Hunyuan3dClientManager:
    """Get the global Hunyuan3D client manager instance."""
    return Hunyuan3dClientManager()


# USD conversion handler for main thread
def _handle_usd_conversion_request(event):
    """Handle USD conversion request on main thread."""
    task_uid = event.get("task_uid")
    glb_path = event.get("glb_path")
    usd_path = event.get("usd_path")
    
    if not all([task_uid, glb_path, usd_path]):
        return
    
    async def convert():
        try:
            def progress_callback(progress: float):
                print(f"[USD Conversion] Task {task_uid} progress: {progress:.1%}")
            
            task_manager = converter.get_instance()
            task = task_manager.create_converter_task(glb_path, usd_path, progress_callback)
            success = await task.wait_until_finished()
            
            client_manager = get_client_manager()
            if success:
                client_manager._handle_conversion_completed(task_uid, True, usd_path)
            else:
                error_msg = task.get_error_message()
                client_manager._handle_conversion_completed(task_uid, False, error_msg)
                
        except Exception as e:
            client_manager = get_client_manager()
            client_manager._handle_conversion_completed(task_uid, False, str(e))
    
    asyncio.ensure_future(convert())


# Set up event handler when module is imported
from carb.eventdispatcher import get_eventdispatcher
_conversion_handler_sub = get_eventdispatcher().observe_event(
    observer_name="Hunyuan3D USD conversion handler",
    event_name="hunyuan3d_start_conversion",
    on_event=_handle_usd_conversion_request
)