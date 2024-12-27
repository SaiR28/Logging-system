import os
import torch
import numpy as np
from PIL import Image
from pathlib import Path
import depth_pro
from typing import Tuple, Dict, Union, Optional

class DepthInference:
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize the Depth Pro inference model.
        
        Args:
            model_path (str, optional): Path to custom model checkpoint. If None, uses default.
        """
        try:
            self.model, self.transform = depth_pro.create_model_and_transforms()
            self.model.eval()
            if torch.cuda.is_available():
                self.model = self.model.cuda()
            self.device = next(self.model.parameters()).device
        except Exception as e:
            raise RuntimeError(f"Failed to initialize model: {str(e)}")

    def load_image(self, image_path: Union[str, Path]) -> Tuple[torch.Tensor, float]:
        """
        Load and preprocess an image for inference.
        
        Args:
            image_path: Path to the input image
            
        Returns:
            Tuple containing preprocessed image tensor and focal length
        """
        try:
            image, _, f_px = depth_pro.load_rgb(image_path)
            image = self.transform(image)
            if torch.cuda.is_available():
                image = image.cuda()
            return image, f_px
        except Exception as e:
            raise ValueError(f"Failed to load image {image_path}: {str(e)}")

    @torch.no_grad()
    def infer(self, image_path: Union[str, Path]) -> Dict[str, np.ndarray]:
        """
        Run depth inference on a single image.
        
        Args:
            image_path: Path to input image
            
        Returns:
            Dictionary containing:
                - depth: Depth map in meters
                - focallength_px: Focal length in pixels
                - confidence: Confidence map (if available)
        """
        try:
            # Load and preprocess image
            image, f_px = self.load_image(image_path)
            
            # Run inference
            prediction = self.model.infer(image, f_px=f_px)
            
            # Convert outputs to numpy arrays
            result = {
                "depth": prediction["depth"].cpu().numpy(),
                "focallength_px": prediction["focallength_px"]
            }
            
            # Add confidence if available
            if "confidence" in prediction:
                result["confidence"] = prediction["confidence"].cpu().numpy()
                
            return result
            
        except Exception as e:
            raise RuntimeError(f"Inference failed: {str(e)}")

    def process_directory(self, input_dir: Union[str, Path], 
                         output_dir: Optional[Union[str, Path]] = None) -> Dict[str, Dict[str, np.ndarray]]:
        """
        Process all images in a directory.
        
        Args:
            input_dir: Directory containing input images
            output_dir: Optional directory to save results
            
        Returns:
            Dictionary mapping filenames to their inference results
        """
        input_dir = Path(input_dir)
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
        results = {}
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
        
        for image_path in input_dir.iterdir():
            if image_path.suffix.lower() in image_extensions:
                try:
                    result = self.infer(image_path)
                    results[image_path.name] = result
                    
                    if output_dir:
                        # Save depth map as normalized PNG
                        depth_map = result["depth"]
                        depth_normalized = ((depth_map - depth_map.min()) / 
                                         (depth_map.max() - depth_map.min()) * 255).astype(np.uint8)
                        depth_image = Image.fromarray(depth_normalized)
                        output_path = output_dir / f"{image_path.stem}_depth.png"
                        depth_image.save(output_path)
                        
                except Exception as e:
                    print(f"Failed to process {image_path}: {str(e)}")
                    continue
                    
        return results

def main():
    """Example usage of the DepthInference class"""
    try:
        # Initialize model
        depth_model = DepthInference()
        
        # Single image inference
        image_path = "path/to/image.jpg"
        result = depth_model.infer(image_path)
        print(f"Depth map shape: {result['depth'].shape}")
        print(f"Focal length: {result['focallength_px']:.2f} pixels")
        
        # Directory processing
        input_dir = "path/to/input/directory"
        output_dir = "path/to/output/directory"
        results = depth_model.process_directory(input_dir, output_dir)
        print(f"Processed {len(results)} images")
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()