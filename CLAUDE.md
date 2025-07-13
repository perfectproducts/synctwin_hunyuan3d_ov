# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

This is an NVIDIA Omniverse Kit SDK-based application repository. Use the following repo tool commands for development:

**Build the project:**
```bash
# Linux
./repo.sh build

# Windows
.\repo.bat build

# Clean build (if needed)
./repo.sh build -c  # or .\repo.bat build -c
```

**Launch applications:**
```bash
# Linux
./repo.sh launch

# Windows  
.\repo.bat launch
```

**Run tests:**
```bash
# Linux
./repo.sh test

# Windows
.\repo.bat test
```

**Create new applications/extensions from templates:**
```bash
# Linux
./repo.sh template new

# Windows
.\repo.bat template new
```

**Package for distribution:**
```bash
# Linux
./repo.sh package

# Windows
.\repo.bat package
```

## Architecture Overview

This is a SyncTwin GenAI Viewer application built on the NVIDIA Omniverse Kit SDK for 3D model generation from 2D images using Hunyuan3D 2.1 technology.

### Main Application
- **synctwin.genai.viewer.kit**: Primary application that provides a graphical interface for loading, manipulating and rendering OpenUSD content with Hunyuan3D integration

### Key Extensions
- **synctwin.hunyuan3d.core**: Core extension providing Hunyuan3D API client and utilities
  - Location: `source/extensions/synctwin.hunyuan3d.core/`
  - API client: `synctwin/hunyuan3d/core/api_client.py`
  - Entry point: `synctwin/hunyuan3d/core/extension.py`

- **synctwin.hunyuan3d.tool**: UI extension providing image-to-3D model generation interface
  - Location: `source/extensions/synctwin.hunyuan3d.tool/`
  - Entry point: `synctwin/hunyuan3d/tool/extension.py`
  - Depends on: `synctwin.hunyuan3d.core`

### Core Components

**Extension System:**
- Uses NVIDIA Omniverse extension architecture
- Extensions defined by `extension.toml` configuration files
- Python-based with UI components using `omni.ui`

**Hunyuan3D Integration:**
- Core API client in `synctwin.hunyuan3d.core` for communicating with Hunyuan3D 2.1 server
- Singleton client manager (`Hunyuan3dClientManager`) that handles all task management
- Asynchronous 3D model generation from 2D images
- GLB to USD conversion pipeline with background processing
- Support for texture generation and background removal
- Modular architecture with separated concerns (core API vs UI)
- Command-based architecture using Omniverse Kit command system

**Client Manager Singleton:**
- `Hunyuan3dClientManager`: Centralized task management
  - Located in `synctwin.hunyuan3d.core.client_manager`
  - Handles multiple simultaneous tasks efficiently
  - Background polling thread for status updates
  - Automatic GLB to USD conversion
  - Progress callbacks and completion notifications
  - Resource cleanup and lifecycle management
  - Global configuration (base URL, poll interval)

**Commands:**
- `Hunyuan3dImageToUsdCommand`: Simple interface to the client manager
  - Located in `synctwin.hunyuan3d.core.commands`
  - Delegates all work to the singleton client manager
  - Supports undo/redo functionality (cancels tasks)
  - Configurable generation parameters
  - Progress callback support for UI integration
  - Returns immediately while processing continues in background

**File Structure:**
- `source/apps/`: Application kit files
- `source/extensions/`: Custom extensions
- `templates/`: Templates for creating new applications/extensions
- `_build/`: Build output directory
- `premake5.lua`: Build configuration

### Development Workflow

1. Extensions are built using the repo tool build system
2. The main application loads extensions automatically based on dependencies in `.kit` files
3. UI is built using Omniverse UI framework (`omni.ui`)
4. 3D models are converted from GLB to USD format for Omniverse compatibility
5. Commands provide undoable operations using `omni.kit.commands.execute()`
6. Testing is done through the repo tool test system

### Using Commands

Execute the Hunyuan3D command (delegates to singleton client manager):

```python
import omni.kit.commands

# Basic usage - client manager handles everything
result = omni.kit.commands.execute(
    "Hunyuan3dImageToUsdCommand",
    image_path="/path/to/image.jpg"
)

if result and result.get("success"):
    task_uid = result.get("task_uid")
    output_path = result.get("output_usd_path")
    print(f"Task started: {task_uid}")
    print(f"Output: {output_path}")
    # Client manager continues processing in background
```

### Advanced Usage

```python
import omni.kit.commands
from synctwin.hunyuan3d.core import get_client_manager

# Configure client manager globally
client_manager = get_client_manager()
client_manager.set_default_base_url("http://my-server:8081")
client_manager.set_poll_interval(3.0)

# Progress callback for UI updates
def progress_callback(message: str):
    print(f"Progress: {message}")

# Multiple simultaneous tasks
for i in range(3):
    result = omni.kit.commands.execute(
        "Hunyuan3dImageToUsdCommand",
        image_path=f"/path/to/image_{i}.jpg",
        texture=True,
        seed=i * 100,
        progress_callback=progress_callback
    )

# Tasks run simultaneously, managed by singleton
```

### Task Management

The singleton client manager provides:
1. **Automatic Processing**: Polls status, downloads GLB, converts to USD
2. **Multiple Tasks**: Handles many simultaneous requests efficiently  
3. **Resource Management**: Cleans up temp files automatically
4. **Progress Tracking**: Callbacks for UI integration
5. **Cancellation**: Via command undo or direct task cancellation
6. **Global Config**: Set defaults for all future commands

Note: Commands create USD files but do not load them into stages. Use additional commands to load USD if needed.

### Key Dependencies
- NVIDIA Omniverse Kit SDK 107.3.0
- Python 3.x with requests library
- OpenUSD for 3D content handling
- RTX rendering capabilities

### Settings and Configuration
- Extension settings stored in persistent settings using `carb.settings`
- Host/port configuration for Hunyuan3D service
- Asset conversion pipeline for GLB to USD

The application serves as a bridge between 2D image inputs and 3D USD scenes in the Omniverse ecosystem, leveraging AI-powered 3D generation technology.