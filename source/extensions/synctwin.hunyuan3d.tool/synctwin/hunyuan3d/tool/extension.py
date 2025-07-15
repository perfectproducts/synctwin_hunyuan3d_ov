# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import omni.ext
import omni.ui as ui
import os
from omni.kit.window.file_importer import get_file_importer
import carb.settings
from omni.kit.window.popup_dialog import FormDialog
from synctwin.hunyuan3d.core import api_client
import omni.kit.commands
import omni.kit.asset_converter as converter
import asyncio
HUNYUAN3D_SETTINGS_HOST = "/persistent/hunyuan3d/host"
HUNYUAN3D_SETTINGS_PORT = "/persistent/hunyuan3d/port"

GENERATE_BUTTON_TEXT = "Generate 3D"


# Any class derived from `omni.ext.IExt` in the top level module (defined in
# `python.modules` of `extension.toml`) will be instantiated when the extension
# gets enabled, and `on_startup(ext_id)` will be called. Later when the
# extension gets disabled on_shutdown() is called.
class Hunyuan3DExtension(omni.ext.IExt):
    """This extension manages a simple counter UI."""
    # ext_id is the current extension id. It can be used with the extension
    # manager to query additional information, like where this extension is
    # located on the filesystem.
    def on_startup(self, _ext_id):
        """This is called every time the extension is activated."""
        print("[synctwin.hunyuan3d.tool] Extension startup")

        self._data_dir = os.path.dirname(os.path.realpath(__file__))+"/../../../data"
        self._image_path = None
        settings = carb.settings.get_settings()
        self._service_host = settings.get_as_string(HUNYUAN3D_SETTINGS_HOST)
        if self._service_host == "":
            self._service_host = "localhost"
        self._service_port = settings.get_as_int(HUNYUAN3D_SETTINGS_PORT)
        if self._service_port == 0:
            self._service_port = 8081

        self._empty_image_path = f"{self._data_dir}/image_icon.svg"
        self._window = ui.Window(
            "Hunyuan3D 2.1 Image To 3D", width=400, height=360
        )

        with self._window.frame:
            with ui.VStack():
                with ui.HStack():
                    # center the image
                    ui.Spacer()
                    self.image_preview = ui.Image(width=256, height=256, alignment=ui.Alignment.CENTER)
                    ui.Spacer()
                with ui.HStack():
                    self.generate_button = ui.Button(GENERATE_BUTTON_TEXT, clicked_fn=self.on_generate_3d_clicked,height=40)
                    ui.Button(image_url=f"{self._data_dir}/image_icon_white.svg", clicked_fn=self.on_select_image_clicked,height=40, width=40)
                    # we dont have anything to configure yet
                    ui.Button(image_url=f"{self._data_dir}/settings.svg", clicked_fn=self.on_configure_clicked,
                              height=40, width=40, tooltip="configure", enabled=True, visible=True)
                with ui.HStack():
                    #self.health_image = ui.Image(width=25, height=25, alignment=ui.Alignment.CENTER)
                    self.health_label = ui.Label("[health info]")
                    self.host_label = ui.Label("[host info]")
                    ui.Spacer()


        self._uid = None
        self.update_image()
        self.update_host_info()

    @property
    def _base_url(self):
        return f"http://{self._service_host}:{self._service_port}"

    def update_host_info(self):
        health_status = "(Online)" if api_client.is_healthy(base_url=self._base_url) else "(Offline)"
        self.health_label.text = health_status
        self.host_label.text = f"Host: {self._service_host}:{self._service_port}"

    def progress_callback(self, progress: float):
        print(f"convert progress: {progress}")
    
    def on_progress_update(self, message: str):
        print(f"generation progress: {message}")
        
        # Update button text based on progress message
        if "Generation started" in message:
            self.generate_button.text = "Starting..."
        elif "Status: processing" in message:
            self.generate_button.text = "Processing..."
        elif "Status: texturing" in message:
            self.generate_button.text = "Texturing..."
        elif "Status: converting" in message or "Converting GLB to USD" in message:
            self.generate_button.text = "Converting..."
        elif "downloading" in message.lower():
            self.generate_button.text = "Downloading..."
        else:
            # For any other status, show "generating..."
            self.generate_button.text = "Generating..."

    async def convert(self, input_asset_path, output_asset_path):
        task_manager = converter.get_instance()
        task = task_manager.create_converter_task(input_asset_path, output_asset_path, self.progress_callback)
        success = await task.wait_until_finished()

        if not success:
            detailed_status_code = task.get_status()
            detailed_status_error_string = task.get_error_message()
            print(f"Failed to convert asset: {detailed_status_error_string} {detailed_status_code}")
            return False
        print(f"Asset converted successfully: {output_asset_path}")
        return True

    def on_task_completed(self, task_uid: str, success: bool, path_or_error: str):
        """Callback for when a task completes."""
        print(f"Task {task_uid} completed: success={success}, result={path_or_error}")
        
        # Reset UI state
        self.generate_button.text = GENERATE_BUTTON_TEXT
        self.generate_button.enabled = True
        self._uid = None
        
        if success:
            # USD file was created successfully, optionally load it
            try:
                asyncio.ensure_future(omni.usd.get_context().open_stage_async(path_or_error))
            except Exception as e:
                print(f"Failed to open USD stage: {e}")
        else:
            print(f"Generation failed: {path_or_error}")

    def on_open_image_handler(self,
                              filename: str,
                              dirname: str,
                              extension: str = "",
                              selections: list = []):
        print(f"> open '{filename}{extension}' from '{dirname}' with additional selections '{selections}'")
        if not dirname.endswith("/"):
            dirname += "/"
        filepath = f"{dirname}{filename}{extension}"
        self._image_path = filepath
        self.update_image()

    def on_select_image_clicked(self):
        file_importer = get_file_importer()
        if not file_importer:
            return
        file_importer.show_window(
            title="open image",
            import_button_label="open",
            import_handler=self.on_open_image_handler,
            show_only_folders=False,
            file_extension_types=[("*.png", "PNG files"),
                                  ("*.jpg", "JPG files"),
                                  ("*.jpeg", "JPEG files")],
            file_extension="png")

    def update_image(self):
        print("update image", self._image_path)
        if self._image_path is None:
            self.image_preview.source_url = self._empty_image_path
            self.generate_button.enabled = False
            self.generate_button.tooltip = "Select an image to generate a 3D model"
        else:
            self.image_preview.source_url = self._image_path
            self.generate_button.enabled = True
            self.generate_button.tooltip = "Generate 3D model"

    def on_generate_3d_clicked(self):
        print("generate 3d clicked")
        if self._image_path is None:
            print("no image selected")
            return
        if self._uid is None:
            try:
                # Execute the Hunyuan3D command
                success, result = omni.kit.commands.execute(
                    "Hunyuan3dImageTo3d",
                    image_path=self._image_path,
                    base_url=f"http://{self._service_host}:{self._service_port}",
                    remove_background=True,
                    texture=False,
                    seed=1234,
                    progress_callback=self.on_progress_update,
                    completion_callback=self.on_task_completed
                )
                
                if success and result and result.get("success"):
                    self._uid = result.get("task_uid")
                    self.generate_button.enabled = False
                    self.generate_button.text = "generating..."
                    print(f"started generating 3d model with uid {self._uid}")
                else:
                    print("Failed to start generation")
                    
            except Exception as e:
                print(f"Command execution failed: {e}")
        else:
            print(f"already generating 3d model with uid {self._uid}")

    def _on_settings_ok(self, dialog: FormDialog):
        values = dialog.get_values()
        self._service_host = values["host"]
        self._service_port = values["port"]
        settings = carb.settings.get_settings()

        settings.set(HUNYUAN3D_SETTINGS_HOST, self._service_host)
        settings.set(HUNYUAN3D_SETTINGS_PORT, self._service_port)
        self.update_host_info()
        dialog.hide()

    # build the dialog just by adding field_defs
    def _build_settings_dialog(self) -> FormDialog:

        field_defs = [
            FormDialog.FieldDef("host", "host:  ", ui.StringField, self._service_host),
            FormDialog.FieldDef("port", "port:  ", ui.IntField, self._service_port),
        ]
        dialog = FormDialog(
            title="Settings",
            message="Please specify the following paths:",
            field_defs=field_defs,
            ok_handler=self._on_settings_ok,
        )
        return dialog

    def on_configure_clicked(self):
        dlg = self._build_settings_dialog()
        dlg.show()


    def on_shutdown(self):
        """This is called every time the extension is deactivated. It is used
        to clean up the extension state."""
        print("[synctwin.hunyuan3d.tool] Extension shutdown")
        
        # Cancel any running task
        if self._uid:
            try:
                omni.kit.commands.execute("Undo")
            except Exception as e:
                print(f"Failed to cancel task on shutdown: {e}")
