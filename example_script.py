#!/usr/bin/env python3
"""
Example script showing how to use the Hunyuan3dImageToUsdCommand with Client Manager

This script demonstrates how to call the command to generate a USD file from an image.
The command now uses a singleton client manager that handles all task management.
"""

import omni.kit.commands

def main():
    """Main function to demonstrate the Hunyuan3D command usage."""
    
    # Example 1: Basic usage with minimal parameters
    print("Example 1: Basic image to USD conversion")
    result = omni.kit.commands.execute(
        "Hunyuan3dImageToUsdCommand",
        image_path="/path/to/your/image.jpg"
    )
    
    if result and result.get("success"):
        print(f"✅ Generation started successfully!")
        print(f"Task ID: {result.get('task_uid')}")
        print(f"Output will be saved to: {result.get('output_usd_path')}")
        print("The client manager will handle polling and conversion in the background...")
    else:
        print("❌ Failed to start generation")

    # Example 2: Advanced usage with custom parameters and progress tracking
    print("\nExample 2: Advanced usage with progress tracking")
    
    def progress_callback(message: str):
        print(f"🔄 Progress: {message}")
    
    result = omni.kit.commands.execute(
        "Hunyuan3dImageToUsdCommand",
        image_path="/path/to/your/image.png",
        output_usd_path="/custom/output/path/my_model.usd",
        base_url="http://localhost:8081",
        remove_background=True,
        texture=True,
        seed=42,
        octree_resolution=512,
        num_inference_steps=10,
        guidance_scale=7.5,
        progress_callback=progress_callback
    )
    
    if result and result.get("success"):
        print(f"✅ Advanced generation started!")
        print(f"Task ID: {result.get('task_uid')}")
        print(f"Custom output path: {result.get('output_usd_path')}")
        print("Client manager handles everything automatically!")
    else:
        print("❌ Failed to start advanced generation")

    # Example 3: Multiple simultaneous tasks
    print("\nExample 3: Multiple simultaneous tasks")
    
    task_ids = []
    for i in range(3):
        try:
            result = omni.kit.commands.execute(
                "Hunyuan3dImageToUsdCommand",
                image_path=f"/path/to/image_{i}.jpg",
                seed=i * 100
            )
            if result and result.get("success"):
                task_id = result.get('task_uid')
                task_ids.append(task_id)
                print(f"✅ Task {i+1} started with ID: {task_id}")
        except Exception as e:
            print(f"❌ Task {i+1} failed: {e}")
    
    print(f"🎯 Started {len(task_ids)} simultaneous tasks!")
    print("The singleton client manager will process all tasks efficiently.")

    # Example 4: Accessing the client manager directly
    print("\nExample 4: Direct client manager access")
    
    # Get the client manager singleton
    from synctwin.hunyuan3d.core import get_client_manager
    client_manager = get_client_manager()
    
    # Set global configuration
    client_manager.set_default_base_url("http://my-server:8081")
    client_manager.set_poll_interval(3.0)
    
    print("✅ Client manager configured globally")
    
    # Now all commands will use these settings by default
    result = omni.kit.commands.execute(
        "Hunyuan3dImageToUsdCommand",
        image_path="/path/to/image.jpg"
        # base_url will use the default we just set
    )

    # Example 5: Error handling and task cancellation via undo
    print("\nExample 5: Task cancellation via undo")
    try:
        result = omni.kit.commands.execute(
            "Hunyuan3dImageToUsdCommand",
            image_path="/path/to/image.jpg"
        )
        
        if result and result.get("success"):
            task_uid = result.get('task_uid')
            print(f"✅ Task started: {task_uid}")
            
            # Simulate wanting to cancel the task
            print("🔄 Simulating task cancellation via undo...")
            omni.kit.commands.undo()  # This will cancel the task
            print("✅ Task cancelled via undo")
            
    except Exception as e:
        print(f"❌ Command failed with error: {e}")

if __name__ == "__main__":
    main()