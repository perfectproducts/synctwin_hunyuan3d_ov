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

import omni.ext
import omni.kit.commands


# Functions and vars are available to other extensions as usual in python:
# `synctwin.hunyuan3d.core.some_public_function(x)`
def some_public_function(x: int):
    """This is a public function that can be called from other extensions."""
    print(f"[synctwin.hunyuan3d.core] some_public_function was called with {x}")
    return x**x


# Any class derived from `omni.ext.IExt` in the top level module (defined in
# `python.modules` of `extension.toml`) will be instantiated when the extension
# gets enabled, and `on_startup(ext_id)` will be called. Later when the
# extension gets disabled on_shutdown() is called.
class Hunyuan3DCoreExtension(omni.ext.IExt):
    """Hunyuan3D Core extension that provides API client, client manager singleton, and commands."""
    
    def on_startup(self, _ext_id):
        """This is called every time the extension is activated."""
        print("[synctwin.hunyuan3d.core] Extension startup")
        
        # Initialize the client manager singleton
        # This ensures the singleton is created and starts its polling thread
        from .client_manager import get_client_manager
        self._client_manager = get_client_manager()
        
        # Subscribe client manager to hunyuan3d_start_conversion event
        self._client_manager.subscribe_to_conversion_events()
        print("[synctwin.hunyuan3d.core] Client manager singleton initialized")
        
        # Register the Hunyuan3D command
        # Commands are automatically discovered when they inherit from omni.kit.commands.Command
        # and are in a public extension module, but we can register them explicitly for clarity
        from .commands import Hunyuan3dImageTo3d
        
        try:
            omni.kit.commands.register(Hunyuan3dImageTo3d)
            print("[synctwin.hunyuan3d.core] Hunyuan3dImageTo3d registered successfully")
        except Exception as e:
            print(f"[synctwin.hunyuan3d.core] Warning: Failed to register command: {e}")

    def on_shutdown(self):
        """This is called every time the extension is deactivated. It is used
        to clean up the extension state."""
        print("[synctwin.hunyuan3d.core] Extension shutdown")
        
        # Shutdown the client manager singleton
        if hasattr(self, '_client_manager') and self._client_manager:
            try:
                self._client_manager.shutdown()
                print("[synctwin.hunyuan3d.core] Client manager shutdown complete")
            except Exception as e:
                print(f"[synctwin.hunyuan3d.core] Warning: Failed to shutdown client manager: {e}")
        
        # Unregister command
        try:
            from .commands import Hunyuan3dImageTo3d
            omni.kit.commands.unregister(Hunyuan3dImageTo3d)
            print("[synctwin.hunyuan3d.core] Hunyuan3dImageTo3d unregistered")
        except Exception as e:
            print(f"[synctwin.hunyuan3d.core] Warning: Failed to unregister command: {e}")
    
    def get_client_manager(self):
        """Get the client manager instance (for external access if needed)."""
        return getattr(self, '_client_manager', None)
