# UDIM Wireframe Exporter with Live Preview
# Requirements: Pillow (PIL)
#   pip install pillow
#
# Features:
# - Parses OBJ UVs and faces (uses vt indices from f statements)
# - Groups faces by UDIM tile (Maya-style numbering)
# - Renders each tile to PNG at chosen resolution
# - Optional 2x supersampling (anti-aliasing) with Lanczos downscale
# - Line thickness control
# - Color scheme toggle: white bg/black wireframe or inverted
# - Base filename control
# - Live thumbnail preview as tiles are saved (64x64), arranged in a UDIM-style 10-wide grid
# - Scrollable preview area


# I take no credit for this, only the vibe with chatgpt
# if you're starting from scratch, pip install pillow matplotlib
# if you find this useful, either send me money or
# a link to the art that you've done :)

#andy.crook@gmail.com

import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageDraw, ImageTk
import os
from typing import List, Tuple, Dict, Callable, Optional

# ----------------------------- OBJ Parsing -----------------------------

def parse_obj(path: str) -> Tuple[List[Tuple[float, float]], List[List[int]]]:
    """Parse UV coords (vt) and faces (f) from an OBJ.
    Returns (uvs, faces_uv_idx) where uvs is a list of (u, v) floats and faces
    is a list of lists of UV indices (0-based). Faces without UVs are skipped.
    """
    uvs: List[Tuple[float, float]] = []
    faces: List[List[int]] = []

    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if not line:
                continue
            if line.startswith('vt '):
                parts = line.strip().split()
                if len(parts) >= 3:
                    try:
                        u = float(parts[1])
                        v = float(parts[2])
                        uvs.append((u, v))
                    except ValueError:
                        continue
            elif line.startswith('f '):
                parts = line.strip().split()[1:]
                uv_indices: List[int] = []
                for p in parts:
                    # supported formats: v, v/vt, v//vn, v/vt/vn
                    tokens = p.split('/')
                    if len(tokens) > 1 and tokens[1] != '':
                        try:
                            uv_idx = int(tokens[1]) - 1
                            uv_indices.append(uv_idx)
                        except ValueError:
                            pass
                if uv_indices:
                    faces.append(uv_indices)
    return uvs, faces

# ----------------------------- UDIM Helpers -----------------------------

def uv_to_udim(u: float, v: float) -> int:
    tile_u = int(u)
    tile_v = int(v)
    return 1001 + tile_u + tile_v * 10

# For preview positioning in true UDIM grid (10-wide)
def udim_row_col(udim: int) -> Tuple[int, int]:
    base = udim - 1001
    row = base // 10
    col = base % 10
    return row, col

# ----------------------------- Rendering -----------------------------

def render_udims(
    uvs: List[Tuple[float, float]],
    faces: List[List[int]],
    outdir: str,
    base_name: str,
    size: int = 4096,
    thickness: int = 1,
    aa: bool = True,
    invert: bool = False,
    preview_callback: Optional[Callable[[Image.Image, int], None]] = None,
):
    """Render UDIM tiles as wireframe PNGs.
    preview_callback(img, udim) is called after saving each tile, with img at final size.
    """
    scale = 2 if aa else 1
    work_size = size * scale
    work_thickness = max(1, thickness * scale)

    bg_color = 'black' if invert else 'white'
    line_color = 'white' if invert else 'black'

    # Group faces by UDIM (collect all UVs that contribute to that tile)
    tiles: Dict[int, List[List[Tuple[float, float]]]] = {}
    for face in faces:
        # gather this face's UVs
        try:
            uv_face = [uvs[i] for i in face]
        except IndexError:
            # ignore malformed references
            continue
        # Determine all tiles this face touches (with 5% gutters, faces shouldn't cross tiles)
        udims = {uv_to_udim(u, v) for (u, v) in uv_face}
        for udim in udims:
            tiles.setdefault(udim, []).append(uv_face)

    # Sort by UDIM so previews appear in grid order
    for udim in sorted(tiles.keys()):
        fcs = tiles[udim]
        img = Image.new('RGB', (work_size, work_size), bg_color)
        draw = ImageDraw.Draw(img)
        for face_uvs in fcs:
            # Build points in local [0,1] for that tile, mapped to work_size
            pts = []
            for (u, v) in face_uvs:
                tile_u = int(u)
                tile_v = int(v)
                uu = u - tile_u
                vv = v - tile_v
                x = uu * work_size
                y = (1.0 - vv) * work_size  # flip V
                pts.append((x, y))
            # Draw as polyline (closed)
            n = len(pts)
            if n >= 2:
                for i in range(n):
                    p1 = pts[i]
                    p2 = pts[(i + 1) % n]
                    draw.line([p1, p2], fill=line_color, width=work_thickness)

        # Downsample to target size for antialiasing
        if aa and scale > 1:
            img = img.resize((size, size), Image.LANCZOS)

        # Save
        outpath = os.path.join(outdir, f"{base_name}-{udim}.png")
        img.save(outpath)
        # Preview callback with final sized image
        if preview_callback:
            preview_callback(img, udim)

# ----------------------------- GUI -----------------------------

class UDIMApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title('UDIM Wireframe Exporter')
        # window around 760x600 to show ~10 thumbs across and a few rows
        try:
            self.root.geometry('760x620')
        except Exception:
            pass

        # Top controls
        tk.Label(root, text='Export UDIM wireframes as PNGs').pack(pady=8)

        # Resolution selector
        self.res_choice = tk.IntVar(value=4096)
        res_frame = tk.Frame(root)
        res_frame.pack(pady=4)
        tk.Label(res_frame, text='Output Resolution:').pack(side=tk.LEFT, padx=6)
        tk.OptionMenu(res_frame, self.res_choice, 512, 1024, 2048, 4096, 8192).pack(side=tk.LEFT)

        # Thickness selector
        self.thick_choice = tk.IntVar(value=1)
        thick_frame = tk.Frame(root)
        thick_frame.pack(pady=4)
        tk.Label(thick_frame, text='Line Thickness:').pack(side=tk.LEFT, padx=6)
        tk.OptionMenu(thick_frame, self.thick_choice, 1, 2, 3, 4, 5).pack(side=tk.LEFT)

        # Anti-aliasing
        self.aa_choice = tk.BooleanVar(value=True)
        aa_frame = tk.Frame(root)
        aa_frame.pack(pady=4)
        tk.Checkbutton(aa_frame, text='Enable Anti-Aliasing (2x supersample)', variable=self.aa_choice).pack(side=tk.LEFT)

        # Color invert
        self.invert_choice = tk.BooleanVar(value=False)
        invert_frame = tk.Frame(root)
        invert_frame.pack(pady=4)
        tk.Checkbutton(invert_frame, text='Invert Colors (black bg, white wireframe)', variable=self.invert_choice).pack(side=tk.LEFT)

        # Base filename
        self.base_name = tk.StringVar(value='output')
        base_frame = tk.Frame(root)
        base_frame.pack(pady=4)
        tk.Label(base_frame, text='Base Filename:').pack(side=tk.LEFT, padx=6)
        tk.Entry(base_frame, textvariable=self.base_name, width=20).pack(side=tk.LEFT)

        # Buttons
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=8)
        tk.Button(btn_frame, text='Select OBJ and Export', command=self.run_export).pack(side=tk.LEFT, padx=6)

        # Preview area (scrollable canvas)
        preview_container = tk.Frame(root)
        preview_container.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.canvas = tk.Canvas(preview_container, width=720, height=420, bg='#f0f0f0', highlightthickness=1, highlightbackground='#ccc')
        self.v_scroll = tk.Scrollbar(preview_container, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.v_scroll.set)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Internal frame inside canvas
        self.inner = tk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.inner, anchor='nw')
        self.inner.bind('<Configure>', self._on_frame_configure)
        self.canvas.bind('<Configure>', self._on_canvas_configure)

        # Thumbnail bookkeeping
        self.thumbs: List[ImageTk.PhotoImage] = []  # keep references
        self.thumb_widgets: Dict[int, Tuple[int, int]] = {}  # udim -> (img_id, text_id)
        self.TILE = 64
        self.PAD = 6

    # Canvas size/scroll handling
    def _on_frame_configure(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def _on_canvas_configure(self, event):
        # Keep the inner frame width equal to canvas width
        canvas_width = event.width
        self.canvas.itemconfig(self.canvas_window, width=canvas_width)

    # Preview placement in UDIM grid (10 columns)
    def _place_thumb(self, pil_img: Image.Image, udim: int):
        # Create TK image
        img = pil_img.resize((self.TILE, self.TILE), Image.LANCZOS)
        tk_img = ImageTk.PhotoImage(img)
        self.thumbs.append(tk_img)

        row, col = udim_row_col(udim)
        x = col * (self.TILE + self.PAD)
        y = row * (self.TILE + self.PAD + 12)  # extra room for label

        # Create or update image and label
        if udim in self.thumb_widgets:
            img_id, text_id = self.thumb_widgets[udim]
            self.canvas.itemconfig(img_id, image=tk_img)
            # label remains same
        else:
            img_id = self.canvas.create_image(x, y, image=tk_img, anchor='nw')
            text_id = self.canvas.create_text(x + self.TILE/2, y + self.TILE + 8, text=str(udim))
            self.thumb_widgets[udim] = (img_id, text_id)

        # Update scrollregion immediately for live feel
        self.canvas.update_idletasks()

    def run_export(self):
        # Clear previous preview
        self.canvas.delete('all')
        self.thumb_widgets.clear()
        self.thumbs.clear()
        # Recreate inner window in case it was cleared
        self.inner = tk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.inner, anchor='nw')

        obj_path = filedialog.askopenfilename(filetypes=[('OBJ files', '*.obj')])
        if not obj_path:
            return
        outdir = filedialog.askdirectory()
        if not outdir:
            return

        try:
            uvs, faces = parse_obj(obj_path)
            if not uvs or not faces:
                messagebox.showwarning('No Data', 'No UVs or faces with UVs found in this OBJ.')
                return
        except Exception as e:
            messagebox.showerror('Parse Error', str(e))
            return

        def preview_cb(img: Image.Image, udim: int):
            # Place image on the canvas at its UDIM-based grid spot (10 columns)
            self._place_thumb(img, udim)

        try:
            render_udims(
                uvs=uvs,
                faces=faces,
                outdir=outdir,
                base_name=self.base_name.get().strip() or 'output',
                size=int(self.res_choice.get()),
                thickness=int(self.thick_choice.get()),
                aa=bool(self.aa_choice.get()),
                invert=bool(self.invert_choice.get()),
                preview_callback=preview_cb,
            )
            messagebox.showinfo('Done', f'UDIM templates exported to:\n{outdir}')
        except Exception as e:
            messagebox.showerror('Error', str(e))


if __name__ == '__main__':
    root = tk.Tk()
    app = UDIMApp(root)
    root.mainloop()
