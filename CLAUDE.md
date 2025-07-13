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
- Asynchronous 3D model generation from 2D images
- GLB to USD conversion pipeline in the tool extension
- Support for texture generation and background removal
- Modular architecture with separated concerns (core API vs UI)
- Command-based architecture using Omniverse Kit command system

**Commands:**
- `Hunyuan3dImageToUsdCommand`: Complete pipeline from 2D image to USD file
  - Located in `synctwin.hunyuan3d.core.commands`
  - Starts async 3D generation on server
  - Polls status using background thread (not blocking UI)
  - Downloads GLB model when generation completes
  - Converts GLB to USD using `omni.kit.asset_converter`
  - Creates USD file (does not load into stage)
  - Supports undo/redo functionality with cleanup
  - Configurable generation parameters and polling interval
  - Progress callback support for UI integration

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

To execute the Hunyuan3D command programmatically:

```python
import omni.kit.commands

# Progress callback for UI updates
def progress_callback(message: str):
    print(f"Progress: {message}")

# Complete pipeline from image to USD
result = omni.kit.commands.execute(
    "Hunyuan3dImageToUsdCommand",
    image_path="/path/to/image.jpg",
    output_usd_path="/path/to/output.usd",  # Optional: auto-generated if None
    base_url="http://localhost:8081",
    remove_background=True,
    texture=False,
    seed=1234,
    poll_interval=5.0,   # Seconds between status checks
    progress_callback=progress_callback  # Optional progress updates
)

if result and result.get("success"):
    task_uid = result.get("task_uid")
    output_path = result.get("output_usd_path")
    print(f"Generation started with task ID: {task_uid}")
    print(f"USD will be saved to: {output_path}")
    # Command will continue processing in background
    
    # If you want to load the USD into stage after completion:
    # omni.kit.commands.execute("OpenStage", usd_path=output_path)
```

The command runs the complete pipeline automatically:
1. Sends image to Hunyuan3D server
2. Polls status in background thread (non-blocking)
3. Downloads GLB when generation completes
4. Converts GLB to USD format
5. All steps are undoable with proper cleanup

Note: The command creates the USD file but does not load it into any stage. Use additional commands to load the USD if needed.

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