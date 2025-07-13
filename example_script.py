#!/usr/bin/env python3
"""
Example script showing how to use the Hunyuan3dImageToUsdCommand

This script demonstrates how to call the command to generate a USD file from an image.
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
    else:
        print("❌ Failed to start generation")

    # Example 2: Advanced usage with custom parameters
    print("\nExample 2: Advanced usage with custom parameters")
    
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
        poll_interval=3.0,
        progress_callback=progress_callback
    )
    
    if result and result.get("success"):
        print(f"✅ Advanced generation started!")
        print(f"Task ID: {result.get('task_uid')}")
        print(f"Custom output path: {result.get('output_usd_path')}")
        print("The command will continue processing in the background...")
    else:
        print("❌ Failed to start advanced generation")

    # Example 3: Error handling
    print("\nExample 3: With error handling")
    try:
        result = omni.kit.commands.execute(
            "Hunyuan3dImageToUsdCommand",
            image_path="/path/to/nonexistent/image.jpg"
        )
    except Exception as e:
        print(f"❌ Command failed with error: {e}")

if __name__ == "__main__":
    main()