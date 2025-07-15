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
from typing import Optional, Dict, Any, Callable
import omni.kit.commands
from .api_client import Hunyuan3DAPIError, Hunyuan3DAPIValidationError
from .client_manager import get_client_manager


class Hunyuan3dImageTo3d(omni.kit.commands.Command):
    """
    Command to generate a USD file from a 2D image using Hunyuan3D.
    
    This command delegates to the Hunyuan3dClientManager singleton which handles:
    1. API communication with Hunyuan3D server
    2. Background task status polling
    3. GLB to USD conversion
    4. Progress tracking and completion callbacks
    
    The command is undoable - it will cancel the task and clean up generated files.
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
        progress_callback: Optional[Callable[[str], None]] = None,
        completion_callback: Optional[Callable[[str, bool, str], None]] = None
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
            progress_callback: Optional callback for progress updates (message only)
            completion_callback: Optional callback for task completion (task_uid, success, path_or_error)
        """
        # Store parameters
        self._image_path = image_path
        self._output_usd_path = output_usd_path
        self._base_url = base_url
        self._progress_callback = progress_callback
        self._completion_callback = completion_callback
        
        # Generation parameters
        self._generation_params = {
            "remove_background": remove_background,
            "texture": texture,
            "seed": seed,
            "octree_resolution": octree_resolution,
            "num_inference_steps": num_inference_steps,
            "guidance_scale": guidance_scale,
            "num_chunks": num_chunks,
            "face_count": face_count
        }
        
        # State for undo
        self._task_uid = None
        
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
        Execute the image-to-USD conversion by submitting to client manager.
        
        Returns:
            Dict containing success status, task ID, and file paths
            
        Raises:
            Hunyuan3DAPIError: If the API request fails
            RuntimeError: If the setup fails
        """
        try:
            client_manager = get_client_manager()
            
            # Create progress callback that wraps the user's callback
            def internal_progress_callback(task_uid: str, message: str):
                if self._progress_callback:
                    self._progress_callback(message)
            
            # Create completion callback for tracking
            def completion_callback(task_uid: str, success: bool, path_or_error: str):
                if success:
                    print(f"[Hunyuan3dImageTo3d] Task {task_uid} completed successfully: {path_or_error}")
                else:
                    print(f"[Hunyuan3dImageTo3d] Task {task_uid} failed: {path_or_error}")
                
                # Call user's completion callback if provided
                if self._completion_callback:
                    self._completion_callback(task_uid, success, path_or_error)
            
            # Submit task to client manager
            self._task_uid = client_manager.submit_task(
                image_path=self._image_path,
                output_usd_path=self._output_usd_path,
                generation_params=self._generation_params,
                base_url=self._base_url,
                progress_callback=internal_progress_callback,
                completion_callback=completion_callback
            )
            
            return {
                "success": True,
                "task_uid": self._task_uid,
                "image_path": self._image_path,
                "output_usd_path": self._output_usd_path,
                "generation_params": self._generation_params
            }
            
        except (Hunyuan3DAPIError, Hunyuan3DAPIValidationError) as e:
            raise RuntimeError(f"Hunyuan3D API error: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Failed to start 3D generation: {str(e)}")

    def undo(self):
        """
        Undo the image-to-USD conversion by cancelling the task.
        
        This will:
        1. Cancel the task in the client manager
        2. Clean up any generated files
        """
        try:
            if self._task_uid:
                print(f"[Hunyuan3dImageTo3d] Undoing task {self._task_uid}")
                client_manager = get_client_manager()
                
                # Cancel the task (this will clean up files too)
                cancelled = client_manager.cancel_task(self._task_uid)
                if cancelled:
                    print(f"[Hunyuan3dImageTo3d] Successfully cancelled task {self._task_uid}")
                else:
                    print(f"[Hunyuan3dImageTo3d] Task {self._task_uid} was not found (may have completed)")
            else:
                print("[Hunyuan3dImageTo3d] No task to undo")
                
        except Exception as e:
            print(f"[Hunyuan3dImageTo3d] Warning: Failed to undo: {str(e)}")
        finally:
            # Always clear the task UID, even if cancellation failed
            self._task_uid = None

    def get_task_uid(self) -> Optional[str]:
        """Get the task UID for external tracking."""
        return self._task_uid
    
    def get_task_info(self):
        """Get current task information from client manager."""
        if self._task_uid:
            client_manager = get_client_manager()
            return client_manager.get_task_info(self._task_uid)
        return None