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
from synctwin.hunyuan3d.tool import api_client
import threading
import time
import omni.kit.asset_converter as converter
import tempfile
import base64
from carb.eventdispatcher import get_eventdispatcher, Event
import omni.kit.app
import asyncio


GLB_COMPLETED_EVENT: str = "omni.hunyuan3d.glb_completed"
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


        self._status_check_interval = 5.0
        self._uid = None
        self._status_thread = threading.Thread(target=self.check_status_loop)
        self._status_thread.start()
        self._temp_dir = tempfile.mkdtemp()
        # Events are managed globally through eventdispatcher and can be observed as such.
        # The on_event() function will be called during the next app update after the event is queued.
        self._sub = get_eventdispatcher().observe_event(
            observer_name="glb completed observer",  # a debug name for profiling and debugging
            event_name=GLB_COMPLETED_EVENT,
            on_event=self.on_glb_completed_event
        )
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

    # Event functions receive the event, which has `event_name` and optional arguments.
    # Only events that you are observing will be delivered to your event function
    def on_glb_completed_event(self, e: Event):
        print("on_glb completed event")
        assert e.event_name == GLB_COMPLETED_EVENT
        glb_path = e['glb_path']
        print(f"glb path: {glb_path}")
        # reset the generate button text
        self.generate_button.text = GENERATE_BUTTON_TEXT
        self.generate_button.enabled = True
        # convert the glb to usd, usd path is _image_path basename with .usd extension
        asset_usd_path = f"{os.path.splitext(self._image_path)[0]}.usd"
        if os.path.exists(asset_usd_path):
            os.remove(asset_usd_path)
        # Start conversion in background and queue event when done
        asyncio.ensure_future(self.convert_glb_to_usd(glb_path, asset_usd_path))

    async def convert_glb_to_usd(self, glb_path: str, asset_usd_path: str):
        """Convert GLB to USD and queue the completion event when done."""
        success = await self.convert(glb_path, asset_usd_path)

        if success:
            await omni.usd.get_context().open_stage_async(asset_usd_path)
        else:
            print("Failed to convert GLB to USD")

    def handle_generate_completed(self, model_base64: str):
        print("3d model generated")
        if self._uid is None:
            print("no uid")
            return

        model_data = base64.b64decode(model_base64)
        if model_data is None:
            print("no model data")
            return

        # save the model to the data directory
        glb_path = f"{self._temp_dir}/{self._uid}.glb"
        with open(glb_path, "wb") as f:
            f.write(model_data)
        print(f"model saved to {glb_path}")
        # send event to main thread to convert the glb to usd

        # Queuing the event:
        omni.kit.app.queue_event(GLB_COMPLETED_EVENT,
                                 payload={"glb_path": glb_path})
        self._uid = None

    def check_status_loop(self):
        while True:
            if self._uid is None:
                time.sleep(self._status_check_interval)
                continue
            status = api_client.get_task_status(self._uid, self._base_url)
            print(f"status: {status}")
            if status.status == "completed":
                self.handle_generate_completed(status.model_base64)
            elif status.status == "error":
                print("error generating 3d model")
                self._uid = None
            time.sleep(self._status_check_interval)

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
            self._uid = api_client.generate_3d_model_async_from_image(self._image_path, base_url=f"http://{self._service_host}:{self._service_port}")
            self.generate_button.enabled = False
            self.generate_button.text = "generating..."
            print(f"started generating 3d model with uid {self._uid}")

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
