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
    """Hunyuan3D Core extension that provides API client and commands."""
    
    def on_startup(self, _ext_id):
        """This is called every time the extension is activated."""
        print("[synctwin.hunyuan3d.core] Extension startup")
        
        # Register the Hunyuan3D command
        # Commands are automatically discovered when they inherit from omni.kit.commands.Command
        # and are in a public extension module, but we can register them explicitly for clarity
        from .commands import Hunyuan3dImageToUsdCommand
        
        try:
            omni.kit.commands.register(Hunyuan3dImageToUsdCommand)
            print("[synctwin.hunyuan3d.core] Hunyuan3dImageToUsdCommand registered successfully")
        except Exception as e:
            print(f"[synctwin.hunyuan3d.core] Warning: Failed to register command: {e}")

    def on_shutdown(self):
        """This is called every time the extension is deactivated. It is used
        to clean up the extension state."""
        print("[synctwin.hunyuan3d.core] Extension shutdown")
        
        # Unregister command
        try:
            from .commands import Hunyuan3dImageToUsdCommand
            omni.kit.commands.unregister(Hunyuan3dImageToUsdCommand)
            print("[synctwin.hunyuan3d.core] Hunyuan3dImageToUsdCommand unregistered")
        except Exception as e:
            print(f"[synctwin.hunyuan3d.core] Warning: Failed to unregister command: {e}")
