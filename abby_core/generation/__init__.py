"""
Content Generation Module

Provides generic image and content generation capabilities:
- Image generation from text prompts (Stability AI)
- Image-to-image transformations
- Image upscaling
- Can be used by any adapter (Discord, Web UI, API, etc.)
"""

from .image_generator import ImageGenerator

__all__ = ["ImageGenerator"]
