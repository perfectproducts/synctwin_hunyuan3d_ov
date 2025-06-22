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
        self._service_host = settings.get_as_string("/persistent/hunyuan3d/host")
        if self._service_host == "":
            self._service_host = "localhost"
        self._service_port = settings.get_as_int("/persistent/hunyuan3d/port")
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
                    ui.Button("Generate 3D", clicked_fn=self.on_generate_3d_clicked,height=40)
                    ui.Button(image_url=f"{self._data_dir}/image_icon_white.svg", clicked_fn=self.on_select_image_clicked,height=40, width=40)
                    # we dont have anything to configure yet
                    ui.Button(image_url=f"{self._data_dir}/settings.svg", clicked_fn=self.on_configure_clicked,
                              height=40, width=40, tooltip="configure", enabled=True, visible=True)
        self.update_image()

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
        else:
            self.image_preview.source_url = self._image_path



    def on_generate_3d_clicked(self):
        print("generate 3d clicked")

    def _on_settings_ok(self, dialog: FormDialog):
        values = dialog.get_values()
        self._use_service = values["use_service"]
        self._service_host = values["host"]
        self._service_port = values["port"]
        settings = carb.settings.get_settings()

        settings.set("/persistent/hunyuan3d/host", self._service_host)
        settings.set("/persistent/hunyuan3d/port", self._service_port)
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
