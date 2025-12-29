from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class CoverArtGenerator:
    def __init__(self, assets_dir: Path):
        self.assets_dir = assets_dir
        self.base_image_path = assets_dir / "listenbrainz_cover_base.png"
        
        # Ensure assets dir exists
        if not self.assets_dir.exists():
            self.assets_dir.mkdir(parents=True, exist_ok=True)

    def generate_cover(self, title: str, subtitle: str = "") -> bytes:
        """
        Generates a cover image with title overlay.
        Returns bytes of the JPEG image.
        """
        try:
            if not self.base_image_path.exists():
                logger.error(f"Base image not found at {self.base_image_path}")
                return None

            # Open base image
            with Image.open(self.base_image_path) as img:
                img = img.convert("RGB")
                draw = ImageDraw.Draw(img)
                width, height = img.size

                # Improved Font Sizing & Layout
                # Goal: 
                # Title: Large, Multiline if needed, Top/Center
                # User: Large, Distinct color/weight, Bottom/Center

                # --- LOGIC UPDATE: One Word Per Line ---
                # User requested "Weekly Exploration" -> "Weekly", "Exploration" each on their own line.
                # Also prevent overflow if a word is extremely long.

                import textwrap
                
                # Split by words to force one word per line (User request 1)
                words = title.split()
                if not words:
                    words = [title]
                lines = words

                # --- Dynamic Font Sizing (Prevent Overflow) ---
                # Start with a large font, shrink if any word is wider than image width
                max_width = width * 0.90 # Leave 5% margin on each side
                
                def get_max_word_width(font_obj, words_list):
                    max_w = 0
                    for w in words_list:
                        bbox = draw.textbbox((0, 0), w, font=font_obj)
                        max_w = max(max_w, bbox[2] - bbox[0])
                    return max_w

                # Start slightly larger than before since we have more vertical space
                current_title_size = int(width / 6) 
                
                font_path = self.assets_dir / "font.ttf"
                
                # Iteratively shrink font until it fits
                while current_title_size > 10:
                    try:
                        if font_path.exists():
                             font = ImageFont.truetype(str(font_path), current_title_size)
                        else:
                             # Try system fonts
                             try:
                                 font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", current_title_size)
                             except:
                                 # Fallback to default (ugly, non-scalable usually, but prevents crash)
                                 # Warning: load_default doesn't support size. 
                                 # If we hit this, dynamic sizing fails.
                                 font = ImageFont.load_default()
                                 break 
                        
                        max_w = get_max_word_width(font, lines)
                        if max_w <= max_width:
                            break # Fits!
                        
                        current_title_size -= 2 # Shrink
                    except Exception as e:
                        logger.warning(f"Font sizing error: {e}")
                        break

                # Subtitle (User) Sizing - Make it Prominent
                # Sync subtitle size relative to final title size but slightly smaller
                subtitle_size = int(current_title_size * 0.8)
                try:
                     if font_path.exists():
                         sub_font = ImageFont.truetype(str(font_path), subtitle_size)
                     else:
                         sub_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", subtitle_size)
                except:
                     sub_font = ImageFont.load_default()

                # --- Calculate Layout ---
                line_heights = []
                line_spacing = 10
                for line in lines:
                    bbox = draw.textbbox((0, 0), line, font=font)
                    line_heights.append(bbox[3] - bbox[1])
                
                total_title_h = sum(line_heights) + (len(lines) - 1) * line_spacing
                
                # --- Draw Subtitle (User) ---
                sub_w = 0
                sub_h = 0
                if subtitle:
                    sbbox = draw.textbbox((0, 0), subtitle, font=sub_font)
                    sub_w = sbbox[2] - sbbox[0]
                    sub_h = sbbox[3] - sbbox[1]

                # --- Positioning ---
                # [ Spacer ]
                # [ Title Block ]
                # [ Spacer (Gap) ]
                # [ User Block ]
                # [ Spacer ]
                
                content_gap = 40 
                total_content_h = total_title_h + content_gap + sub_h
                
                start_y = (height - total_content_h) / 2
                
                # Draw Title Lines
                current_y = start_y
                for i, line in enumerate(lines):
                    lbbox = draw.textbbox((0, 0), line, font=font)
                    lw = lbbox[2] - lbbox[0]
                    lx = (width - lw) / 2
                    
                    # Shadow
                    shadow = 4
                    draw.text((lx+shadow, current_y+shadow), line, font=font, fill=(0,0,0))
                    draw.text((lx, current_y), line, font=font, fill=(255, 255, 255))
                    
                    current_y += line_heights[i] + line_spacing
                
                # Draw User
                if subtitle:
                    user_y = current_y + content_gap - line_spacing 
                    sx = (width - sub_w) / 2
                    
                    # Shadow
                    draw.text((sx+3, user_y+3), subtitle, font=sub_font, fill=(0,0,0))
                    # Text - Gold/Yellow
                    draw.text((sx, user_y), subtitle, font=sub_font, fill=(255, 220, 100))

                # Save to bytes
                from io import BytesIO
                out_buffer = BytesIO()
                img.save(out_buffer, format="JPEG", quality=90)
                return out_buffer.getvalue()

        except Exception as e:
            logger.error(f"Failed to generate cover: {e}")
            return None
