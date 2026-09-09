import io
import os
from typing import List, Dict, Any, Tuple, Optional
from PIL import Image, ImageFilter, ImageOps, ImageDraw

_rembg_session = None

def get_rembg_session(model_name: str = "u2netp"):
    """
    Vrátí cached singleton rembg session pro daný model.
    Výchozí model je 'u2netp' (extrémně rychlý, lehký ~4MB ONNX model).
    """
    global _rembg_session
    if _rembg_session is None:
        try:
            import rembg
            # Nastavíme U2NET_HOME, pokud není nastaven
            if "U2NET_HOME" not in os.environ:
                from listing_hub.core.config import DATA_DIR
                os.environ["U2NET_HOME"] = str(DATA_DIR / ".u2net")
            _rembg_session = rembg.new_session(model_name)
        except Exception as e:
            print(f"[PhotoEditor] Varování: Nepodařilo se načíst rembg model '{model_name}': {e}")
            _rembg_session = False
    return _rembg_session if _rembg_session is not False else None

def apply_background_bokeh(
    image_bytes: bytes,
    blur_radius: int = 25,
    ground_gradient: bool = True,
    model_name: str = "u2netp"
) -> bytes:
    """
    Rozostří pozadí fotografie (Bokeh efekt) při zachování ostrého předmětu v popředí.
    Využívá rembg masku a PIL GaussianBlur s volitelným gradientem k zemi.
    """
    with Image.open(io.BytesIO(image_bytes)) as raw_img:
        img = ImageOps.exif_transpose(raw_img)
        if img.mode != "RGB":
            img = img.convert("RGB")

        width, height = img.size
        
        # Získání masky popředí z rembg
        session = get_rembg_session(model_name)
        if session is not None:
            try:
                import rembg
                mask_img = rembg.remove(img, session=session, only_mask=True)
                if mask_img.mode != "L":
                    mask_img = mask_img.convert("L")
            except Exception as e:
                print(f"[PhotoEditor] Chyba při segmentaci rembg: {e}")
                mask_img = None
        else:
            mask_img = None

        # Pokud se nepodařilo vygenerovat masku, vrátíme rozostřený celek nebo původní
        if mask_img is None:
            blurred = img.filter(ImageFilter.GaussianBlur(blur_radius))
            out_buf = io.BytesIO()
            blurred.save(out_buf, format="JPEG", quality=92, optimize=True)
            return out_buf.getvalue()

        # 1. Rozostřené pozadí
        blurred_bg = img.filter(ImageFilter.GaussianBlur(blur_radius))

        # 2. Volitelný gradient k zemi (aby plocha pod předmětem nepůsobila useknutě)
        if ground_gradient:
            # Spodních 20 % výšky plynule zprůhledníme, aby země pod koly / předmětem byla ostřejší
            gradient = Image.new("L", (width, height), 0)
            draw = ImageDraw.Draw(gradient)
            grad_start_y = int(height * 0.75)
            for y in range(grad_start_y, height):
                alpha = int(255 * ((y - grad_start_y) / (height - grad_start_y)))
                draw.line([(0, y), (width, y)], fill=alpha)
            
            # Složíme masku předmětu a gradient země (maximum)
            from PIL import ImageChops
            composite_mask = ImageChops.lighter(mask_img, gradient)
            
            # Mírné zjemnění hran masky (anti-aliasing)
            composite_mask = composite_mask.filter(ImageFilter.GaussianBlur(2))
        else:
            composite_mask = mask_img.filter(ImageFilter.GaussianBlur(2))

        # 3. Sloučení ostrého popředí a rozostřeného pozadí
        final_img = Image.composite(img, blurred_bg, composite_mask)

        out_buf = io.BytesIO()
        final_img.save(out_buf, format="JPEG", quality=92, optimize=True)
        return out_buf.getvalue()

def apply_box_blur(
    image_bytes: bytes,
    box_coords: Tuple[float, float, float, float],
    blur_radius: int = 35
) -> bytes:
    """
    Aplikuje silný frosted blur na zadanou obdélníkovou oblast (např. SPZ, sériové číslo).
    box_coords: (x1, y1, x2, y2) normalizované v rozsahu 0.0 - 1.0.
    """
    with Image.open(io.BytesIO(image_bytes)) as raw_img:
        img = ImageOps.exif_transpose(raw_img)
        if img.mode != "RGB":
            img = img.convert("RGB")

        width, height = img.size
        x1_norm, y1_norm, x2_norm, y2_norm = box_coords

        # Normalizace souřadnic (aby x1 < x2 a y1 < y2)
        min_x = max(0, min(width - 1, int(min(x1_norm, x2_norm) * width)))
        max_x = max(0, min(width, int(max(x1_norm, x2_norm) * width)))
        min_y = max(0, min(height - 1, int(min(y1_norm, y2_norm) * height)))
        max_y = max(0, min(height, int(max(y1_norm, y2_norm) * height)))

        box_w = max_x - min_x
        box_h = max_y - min_y

        if box_w < 2 or box_h < 2:
            out_buf = io.BytesIO()
            img.save(out_buf, format="JPEG", quality=92, optimize=True)
            return out_buf.getvalue()

        # Vyřízneme oblast
        crop_box = (min_x, min_y, max_x, max_y)
        cropped_area = img.crop(crop_box)

        # Aplikujeme silný blur
        blurred_area = cropped_area.filter(ImageFilter.GaussianBlur(blur_radius))

        # Frosted glass efekt: jemný poloprůhledný světlý tón
        frosted_overlay = Image.new("RGB", (box_w, box_h), (255, 255, 255))
        frosted_area = Image.blend(blurred_area, frosted_overlay, alpha=0.15)

        # Mírné zaoblení / zjemnění okrajů
        img.paste(frosted_area, crop_box)

        out_buf = io.BytesIO()
        img.save(out_buf, format="JPEG", quality=92, optimize=True)
        return out_buf.getvalue()

def process_photo_pipeline(image_bytes: bytes, operations: List[Dict[str, Any]]) -> bytes:
    """
    Aplikuje sekvenci úprav na fotografii (např. Bokeh + několik box blurů na SPZ).
    """
    current_bytes = image_bytes
    for op in operations:
        op_type = op.get("type")
        if op_type == "bokeh":
            radius = int(op.get("radius", 25))
            ground_grad = bool(op.get("ground_gradient", True))
            current_bytes = apply_background_bokeh(
                current_bytes,
                blur_radius=radius,
                ground_gradient=ground_grad
            )
        elif op_type in ("blur_box", "box_blur"):
            box = op.get("box")
            if box and len(box) == 4:
                radius = int(op.get("radius", 35))
                current_bytes = apply_box_blur(
                    current_bytes,
                    box_coords=(float(box[0]), float(box[1]), float(box[2]), float(box[3])),
                    blur_radius=radius
                )

    return current_bytes
