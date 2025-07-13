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
Hunyuan3D Commands

Omniverse Kit commands for Hunyuan3D functionality including image-to-USD conversion.
"""

import os
import threading
import time
import tempfile
import base64
import asyncio
from typing import Optional, Dict, Any, Callable
import omni.kit.commands
import omni.kit.asset_converter as converter
import omni.kit.app
import omni.usd
from .api_client import (
    Hunyuan3DAPIClient, 
    GenerationRequest, 
    Hunyuan3DAPIError,
    Hunyuan3DAPIValidationError
)


# Events for communication between background thread and main thread
USD_CONVERSION_COMPLETED_EVENT = "omni.hunyuan3d.usd_completed"
USD_CONVERSION_FAILED_EVENT = "omni.hunyuan3d.usd_failed"


class Hunyuan3dImageToUsdCommand(omni.kit.commands.Command):
    """
    Command to generate a USD file from a 2D image using Hunyuan3D.
    
    This command handles the complete pipeline:
    1. Starts async 3D generation on Hunyuan3D server
    2. Polls task status in background thread
    3. Downloads GLB model when generation is complete
    4. Converts GLB to USD format
    
    The command is undoable - it will clean up generated files.
    Note: This command only creates the USD file, it does not load it into any stage.
    """
    
    def __init__(
        self,
        image_path: str,
        output_usd_path: Optional[str] = None,
        base_url: str = "http://localhost:8081",
        remove_background: bool = True,
        texture: bool = False,
        seed: int = 1234,
        octree_resolution: int = 256,
        num_inference_steps: int = 5,
        guidance_scale: float = 5.0,
        num_chunks: int = 8000,
        face_count: int = 40000,
        poll_interval: float = 5.0,
        progress_callback: Optional[Callable[[str], None]] = None
    ):
        """
        Initialize the Hunyuan3D Image to USD command.
        
        Args:
            image_path: Path to input image file
            output_usd_path: Path for output USD file (auto-generated if None)
            base_url: Base URL of Hunyuan3D API server
            remove_background: Whether to remove background from image
            texture: Whether to generate textures
            seed: Random seed for generation
            octree_resolution: Resolution for octree generation
            num_inference_steps: Number of inference steps
            guidance_scale: Guidance scale for generation
            num_chunks: Number of chunks for processing
            face_count: Target face count for mesh
            poll_interval: Seconds between status checks
            progress_callback: Optional callback for progress updates
        """
        # Store all parameters
        self._image_path = image_path
        self._output_usd_path = output_usd_path
        self._base_url = base_url
        self._remove_background = remove_background
        self._texture = texture
        self._seed = seed
        self._octree_resolution = octree_resolution
        self._num_inference_steps = num_inference_steps
        self._guidance_scale = guidance_scale
        self._num_chunks = num_chunks
        self._face_count = face_count
        self._poll_interval = poll_interval
        self._progress_callback = progress_callback
        
        # State for undo and cleanup
        self._task_uid = None
        self._generated_files = []
        self._temp_dir = None
        self._polling_thread = None
        self._stop_polling = False
        self._event_subscriptions = []
        
        # Validate input
        if not os.path.exists(image_path):
            raise ValueError(f"Image file not found: {image_path}")
            
        # Auto-generate output path if not provided
        if self._output_usd_path is None:
            base_name = os.path.splitext(os.path.basename(image_path))[0]
            self._output_usd_path = os.path.join(
                os.path.dirname(image_path),
                f"{base_name}_hunyuan3d.usd"
            )

    def do(self) -> Dict[str, Any]:
        """
        Execute the image-to-USD conversion pipeline.
        
        Returns:
            Dict containing success status, task ID, and file paths
            
        Raises:
            Hunyuan3DAPIError: If the API request fails
            RuntimeError: If the setup fails
        """
        try:
            # Create temp directory for GLB files
            self._temp_dir = tempfile.mkdtemp()
            
            # Set up event subscriptions for USD conversion completion
            self._setup_event_subscriptions()
            
            # Start 3D generation
            with Hunyuan3DAPIClient(self._base_url) as client:
                request = GenerationRequest.from_image_file(
                    self._image_path,
                    remove_background=self._remove_background,
                    texture=self._texture,
                    seed=self._seed,
                    octree_resolution=self._octree_resolution,
                    num_inference_steps=self._num_inference_steps,
                    guidance_scale=self._guidance_scale,
                    num_chunks=self._num_chunks,
                    face_count=self._face_count
                )
                
                response = client.send_generation_task(request)
                self._task_uid = response.uid
            
            # Start background polling thread
            self._start_polling_thread()
            
            # Report progress
            if self._progress_callback:
                self._progress_callback("Generation started")
            
            return {
                "success": True,
                "task_uid": self._task_uid,
                "image_path": self._image_path,
                "output_usd_path": self._output_usd_path,
                "generation_params": {
                    "remove_background": self._remove_background,
                    "texture": self._texture,
                    "seed": self._seed,
                    "octree_resolution": self._octree_resolution,
                    "num_inference_steps": self._num_inference_steps,
                    "guidance_scale": self._guidance_scale,
                    "num_chunks": self._num_chunks,
                    "face_count": self._face_count
                }
            }
            
        except (Hunyuan3DAPIError, Hunyuan3DAPIValidationError) as e:
            self._cleanup()
            raise RuntimeError(f"Hunyuan3D API error: {str(e)}")
        except Exception as e:
            self._cleanup()
            raise RuntimeError(f"Failed to start 3D generation: {str(e)}")

    def _setup_event_subscriptions(self):
        """Set up event listeners for USD conversion completion."""
        from carb.eventdispatcher import get_eventdispatcher
        
        # Subscribe to conversion completion events
        self._event_subscriptions.append(
            get_eventdispatcher().observe_event(
                observer_name="Hunyuan3D USD completed observer",
                event_name=USD_CONVERSION_COMPLETED_EVENT,
                on_event=self._on_usd_conversion_completed
            )
        )
        
        self._event_subscriptions.append(
            get_eventdispatcher().observe_event(
                observer_name="Hunyuan3D USD failed observer", 
                event_name=USD_CONVERSION_FAILED_EVENT,
                on_event=self._on_usd_conversion_failed
            )
        )

    def _start_polling_thread(self):
        """Start background thread to poll generation status."""
        self._stop_polling = False
        self._polling_thread = threading.Thread(target=self._poll_status_loop, daemon=True)
        self._polling_thread.start()

    def _poll_status_loop(self):
        """Background thread loop to poll generation status."""
        print(f"[Hunyuan3dImageToUsdCommand] Starting status polling for task {self._task_uid}")
        
        while not self._stop_polling and self._task_uid:
            try:
                with Hunyuan3DAPIClient(self._base_url) as client:
                    status_response = client.get_task_status(self._task_uid)
                    
                    print(f"[Hunyuan3dImageToUsdCommand] Task {self._task_uid} status: {status_response.status}")
                    
                    if status_response.status == "completed":
                        self._handle_generation_completed(status_response.model_base64)
                        break
                    elif status_response.status == "error":
                        print(f"[Hunyuan3dImageToUsdCommand] Generation failed: {status_response.message}")
                        if self._progress_callback:
                            self._progress_callback(f"Generation failed: {status_response.message}")
                        break
                    else:
                        # Still processing
                        if self._progress_callback:
                            self._progress_callback(f"Status: {status_response.status}")
                
            except Exception as e:
                print(f"[Hunyuan3dImageToUsdCommand] Error checking status: {e}")
                
            time.sleep(self._poll_interval)
        
        print(f"[Hunyuan3dImageToUsdCommand] Stopped polling for task {self._task_uid}")

    def _handle_generation_completed(self, model_base64: str):
        """Handle completion of 3D generation."""
        print(f"[Hunyuan3dImageToUsdCommand] 3D model generation completed")
        
        if not model_base64:
            print("No model data received")
            if self._progress_callback:
                self._progress_callback("No model data received")
            return
        
        try:
            # Decode and save GLB file
            model_data = base64.b64decode(model_base64)
            glb_path = os.path.join(self._temp_dir, f"{self._task_uid}.glb")
            
            with open(glb_path, "wb") as f:
                f.write(model_data)
            
            self._generated_files.append(glb_path)
            print(f"[Hunyuan3dImageToUsdCommand] GLB saved to: {glb_path}")
            
            if self._progress_callback:
                self._progress_callback("Converting to USD...")
            
            # Start USD conversion asynchronously on main thread
            omni.kit.app.queue_event(
                "start_usd_conversion",
                payload={
                    "command_instance": self,
                    "glb_path": glb_path,
                    "usd_path": self._output_usd_path
                }
            )
            
        except Exception as e:
            print(f"[Hunyuan3dImageToUsdCommand] Error handling completion: {e}")
            if self._progress_callback:
                self._progress_callback(f"Error: {e}")

    def _on_usd_conversion_completed(self, event):
        """Handle USD conversion completion event."""
        command_instance = event.get("command_instance")
        if command_instance is not self:
            return
            
        usd_path = event.get("usd_path")
        print(f"[Hunyuan3dImageToUsdCommand] USD conversion completed: {usd_path}")
        
        if self._progress_callback:
            self._progress_callback("USD conversion completed")

    def _on_usd_conversion_failed(self, event):
        """Handle USD conversion failure event."""
        command_instance = event.get("command_instance")
        if command_instance is not self:
            return
            
        error_msg = event.get("error", "Unknown error")
        print(f"[Hunyuan3dImageToUsdCommand] USD conversion failed: {error_msg}")
        
        if self._progress_callback:
            self._progress_callback(f"USD conversion failed: {error_msg}")

    def undo(self):
        """
        Undo the image-to-USD conversion.
        
        This will:
        1. Stop any running polling thread
        2. Remove generated files
        3. Clean up event subscriptions
        """
        try:
            print(f"[Hunyuan3dImageToUsdCommand] Undoing command")
            
            # Stop polling
            self._stop_polling = True
            if self._polling_thread and self._polling_thread.is_alive():
                self._polling_thread.join(timeout=1.0)
            
            # Clean up
            self._cleanup()
            
        except Exception as e:
            print(f"[Hunyuan3dImageToUsdCommand] Warning: Failed to fully undo: {str(e)}")

    def _cleanup(self):
        """Clean up generated files and resources."""
        # Remove generated files
        for file_path in self._generated_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"[Hunyuan3dImageToUsdCommand] Removed: {file_path}")
            except Exception as e:
                print(f"[Hunyuan3dImageToUsdCommand] Failed to remove {file_path}: {e}")
        
        # Remove temp directory
        if self._temp_dir and os.path.exists(self._temp_dir):
            try:
                import shutil
                shutil.rmtree(self._temp_dir)
                print(f"[Hunyuan3dImageToUsdCommand] Removed temp dir: {self._temp_dir}")
            except Exception as e:
                print(f"[Hunyuan3dImageToUsdCommand] Failed to remove temp dir: {e}")
        
        # Clean up event subscriptions
        for subscription in self._event_subscriptions:
            try:
                subscription.unsubscribe()
            except Exception as e:
                print(f"[Hunyuan3dImageToUsdCommand] Failed to unsubscribe: {e}")
        
        self._generated_files.clear()
        self._event_subscriptions.clear()


# Helper function to handle USD conversion on the main thread
def _convert_glb_to_usd_async(glb_path: str, usd_path: str, command_instance):
    """Convert GLB to USD asynchronously and send completion event."""
    
    async def convert():
        try:
            def progress_callback(progress: float):
                print(f"[USD Conversion] Progress: {progress:.1%}")
            
            task_manager = converter.get_instance()
            task = task_manager.create_converter_task(glb_path, usd_path, progress_callback)
            success = await task.wait_until_finished()
            
            if success:
                command_instance._generated_files.append(usd_path)
                omni.kit.app.queue_event(
                    USD_CONVERSION_COMPLETED_EVENT,
                    payload={
                        "command_instance": command_instance,
                        "usd_path": usd_path
                    }
                )
            else:
                error_msg = task.get_error_message()
                omni.kit.app.queue_event(
                    USD_CONVERSION_FAILED_EVENT,
                    payload={
                        "command_instance": command_instance,
                        "error": error_msg
                    }
                )
                
        except Exception as e:
            omni.kit.app.queue_event(
                USD_CONVERSION_FAILED_EVENT,
                payload={
                    "command_instance": command_instance,
                    "error": str(e)
                }
            )
    
    asyncio.ensure_future(convert())


# Register event handler for starting USD conversion on main thread
def _on_start_usd_conversion(event):
    """Event handler to start USD conversion on main thread."""
    command_instance = event.get("command_instance")
    glb_path = event.get("glb_path")
    usd_path = event.get("usd_path")
    
    if command_instance and glb_path and usd_path:
        _convert_glb_to_usd_async(glb_path, usd_path, command_instance)


# Set up the conversion event handler when module is imported
from carb.eventdispatcher import get_eventdispatcher
_conversion_event_sub = get_eventdispatcher().observe_event(
    observer_name="USD conversion starter",
    event_name="start_usd_conversion", 
    on_event=_on_start_usd_conversion
)