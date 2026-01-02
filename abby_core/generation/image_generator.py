"""
Image Generation Service using Stability AI API

Provides text-to-image, image-to-image, and upscaling capabilities.
This is a generic service that can be used by any adapter (Discord, Web, API, etc.).
"""

import aiohttp
import base64
from typing import Optional, Tuple, Dict
from abby_core.observability.logging import setup_logging, logging

setup_logging()
logger = logging.getLogger(__name__)


class ImageGenerator:
    """Generic image generation service using Stability AI."""
    
    # Style presets available
    STYLE_PRESETS = {
        "3d-model": "3d-model",
        "analog-film": "analog-film",
        "anime": "anime",
        "cinematic": "cinematic",
        "comic-book": "comic-book",
        "digital-art": "digital-art",
        "enhance": "enhance",
        "fantasy-art": "fantasy-art",
        "isometric": "isometric",
        "line-art": "line-art",
        "low-poly": "low-poly",
        "modeling-compound": "modeling-compound",
        "neon-punk": "neon-punk",
        "origami": "origami",
        "photographic": "photographic",
        "pixel-art": "pixel-art",
        "tile-texture": "tile-texture"
    }
    
    def __init__(self, api_key: str, api_host: str = "https://api.stability.ai"):
        """
        Initialize image generator.
        
        Args:
            api_key: Stability AI API key
            api_host: API host URL (default: Stability AI)
        """
        self.api_key = api_key
        self.api_host = api_host
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        
        logger.info(f"[🎨] Image generator initialized with {api_host}")
    
    async def text_to_image(
        self,
        prompt: str,
        style_preset: str = "enhance",
        width: int = 1024,
        height: int = 1024,
        steps: int = 50,
        seed: int = 0,
        cfg_scale: float = 7.0,
    ) -> Tuple[bool, Optional[bytes], str]:
        """
        Generate image from text prompt.
        
        Args:
            prompt: Text description of desired image
            style_preset: Art style (default: "enhance")
            width: Image width in pixels (default: 1024)
            height: Image height in pixels (default: 1024)
            steps: Generation steps/quality (default: 50)
            seed: Random seed for reproducibility (default: 0)
            cfg_scale: Guidance scale (default: 7.0)
            
        Returns:
            Tuple of (success, image_bytes, message)
        """
        try:
            # Validate style preset
            style = style_preset.lower()
            if style not in self.STYLE_PRESETS:
                style = "enhance"
                logger.info(f"Invalid style preset, using: enhance")
            
            # Build request body
            body = {
                "width": width,
                "height": height,
                "steps": steps,
                "seed": seed,
                "cfg_scale": cfg_scale,
                "samples": 1,
                "style_preset": self.STYLE_PRESETS[style],
                "text_prompts": [
                    {
                        "text": prompt,
                        "weight": 1
                    },
                    {
                        "text": "blurry, bad, watermark, low quality, low resolution, low res, signature, deformed, misshapen",
                        "weight": -1
                    }
                ],
            }
            
            # Call API
            url = f"{self.api_host}/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, json=body, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"API returned {response.status}: {error_text}")
                    
                    data = await response.json()
            
            # Extract image data
            if "artifacts" not in data or len(data["artifacts"]) == 0:
                return False, None, "No image generated. Please try again."
            
            image_b64 = data["artifacts"][0]["base64"]
            image_bytes = base64.b64decode(image_b64)
            
            logger.info(f"[✅] Image generated successfully ({len(image_bytes)/1024:.1f}KB)")
            return True, image_bytes, "Image generated successfully"
        
        except aiohttp.ClientError as e:
            logger.error(f"[❌] API request failed: {str(e)}")
            return False, None, f"Failed to generate image: {str(e)}"
        except Exception as e:
            logger.error(f"[❌] Generation error: {str(e)}")
            return False, None, f"Error: {str(e)}"
    
    async def image_to_image(
        self,
        image_data: bytes,
        prompt: str,
        style_preset: str = "enhance",
        strength: float = 0.35,
        steps: int = 30,
    ) -> Tuple[bool, Optional[bytes], str]:
        """
        Generate image from another image and text prompt.
        
        Args:
            image_data: Input image bytes (PNG or JPG)
            prompt: Text description for modification
            style_preset: Art style (default: "enhance")
            strength: How much to modify (0-1, default: 0.35)
            steps: Generation steps (default: 30)
            
        Returns:
            Tuple of (success, image_bytes, message)
        """
        try:
            # Validate style preset
            style = style_preset.lower()
            if style not in self.STYLE_PRESETS:
                style = "enhance"
            
            url = f"{self.api_host}/v1/generation/stable-diffusion-xl-1024-v1-0/image-to-image"
            
            async with aiohttp.ClientSession() as session:
                form = aiohttp.FormData()
                form.add_field("init_image", image_data, filename="image.png", content_type="image/png")
                form.add_field("image_strength", str(strength))
                form.add_field("init_image_mode", "IMAGE_STRENGTH")
                form.add_field("text_prompts[0][text]", prompt)
                form.add_field("cfg_scale", "7")
                form.add_field("samples", "1")
                form.add_field("steps", str(steps))
                form.add_field("style_preset", self.STYLE_PRESETS[style])
                
                async with session.post(url, headers={"Authorization": f"Bearer {self.api_key}"}, data=form, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"API returned {response.status}: {error_text}")
                    
                    data = await response.json()
            
            # Extract image
            if "artifacts" not in data or len(data["artifacts"]) == 0:
                return False, None, "No image generated. Please try again."
            
            image_b64 = data["artifacts"][0]["base64"]
            image_bytes = base64.b64decode(image_b64)
            
            logger.info(f"[✅] Image transformed successfully ({len(image_bytes)/1024:.1f}KB)")
            return True, image_bytes, "Image transformed successfully"
        
        except Exception as e:
            logger.error(f"[❌] Image-to-image error: {str(e)}")
            return False, None, f"Error: {str(e)}"
    
    async def upscale_image(
        self,
        image_data: bytes,
        width: int = 2048,
    ) -> Tuple[bool, Optional[bytes], str]:
        """
        Upscale an existing image (2x resolution increase).
        
        Args:
            image_data: Input image bytes
            width: Target width in pixels (default: 2048 for 2x upscale from 1024)
            
        Returns:
            Tuple of (success, image_bytes, message)
        """
        try:
            url = f"{self.api_host}/v1/generation/esrgan-v1-x2plus/image-to-image/upscale"
            
            async with aiohttp.ClientSession() as session:
                form = aiohttp.FormData()
                form.add_field("image", image_data, filename="image.png", content_type="image/png")
                form.add_field("width", str(width))
                
                headers = {
                    "Accept": "image/png",
                    "Authorization": f"Bearer {self.api_key}"
                }
                
                async with session.post(url, headers=headers, data=form, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"API returned {response.status}: {error_text}")
                    
                    image_bytes = await response.content.read()
            
            logger.info(f"[✅] Image upscaled successfully ({len(image_bytes)/1024:.1f}KB)")
            return True, image_bytes, "Image upscaled successfully"
        
        except Exception as e:
            logger.error(f"[❌] Upscale error: {str(e)}")
            return False, None, f"Error: {str(e)}"
    
    @staticmethod
    def get_available_styles() -> Dict[str, str]:
        """Get available style presets."""
        return ImageGenerator.STYLE_PRESETS.copy()
