import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import cv2
import numpy as np
import random

class VicStatePainter:
    def __init__(self, root):
        self.root = root
        self.root.title("State Painter")
        self.root.geometry("1800x1000")
        self.image = None
        self.image_array = None
        self.original_image_array = None

        self.x = 0
        self.y = 0   
        self.state_id = 1
        self.zoom_in = 0
        self.max_zoom = 1

        self.scale = 1
        self.p_scale = 1
        self.delta = 1.3

        self.width = 8192
        self.height = 3616 

        self.vec = [0,0]

        self.state_data = ""
        self.state_colors = {}
        self.all_states = []
        self.hex_codes = []
        self.current_state_color = self.generate_random_color()
        self.highlighted_provinces = set()
        self.used_state_ids = set()

        self.special_assignments = {"city": None, "port": None, "farn": None, "mine": None, "wood": None}
        self.current_assignment = None
        
        self.create_widgets()

    def choose_image(self):
        file_path = filedialog.askopenfilename(filetypes=[("PNG files", "*.png")])
        self.image = Image.open(file_path)
        self.width, self.height = self.image.size
        self.image_array = np.array(self.image)
        self.original_image_array = self.image_array.copy()
        self.update_image()

    def update_image(self, event = None):
        self.image = Image.fromarray(self.image_array)

        cx = self.canvas.canvasx(0)
        cy = self.canvas.canvasy(0)
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()

        endx = int(cw / self.scale)
        endy = int(ch / self.scale)

        if(self.zoom_in != 0):  
            currX = int(self.x / self.p_scale) + self.vec[0]
            currY = int(self.y / self.p_scale) + self.vec[1]

            self.vec[0] = int(currX - (self.x / self.scale))
            self.vec[1] = int(currY - (self.y / self.scale))

        self.vec[0] =  max(0, self.vec[0])
        self.vec[1] =  max(0, self.vec[1])

        ddx = (endx + self.vec[0]) - self.image.width
        ddy = (endy + self.vec[1])  - self.image.height

        if(ddx > 0):
            self.vec[0] = self.vec[0] - ddx
        if(ddy > 0):
            self.vec[1] = self.vec[1] - ddy

        newX = self.vec[0] + (cx / self.scale)
        newY = self.vec[1] + (cy / self.scale)
        visible_img = self.image.crop((newX, newY, newX + endx, newY + endy))
        visible_img = visible_img.resize((cw, ch), Image.NEAREST)
    
        self.tk_image = ImageTk.PhotoImage(visible_img)
        self.canvas.delete("all")
        self.canvas.create_image(cx, cy, anchor="nw", image=self.tk_image)

        self.canvas.configure(scrollregion=(0, 0, (self.width * self.scale), (self.height * self.scale)))
    

    def move_from(self, event):
        self.x = self.canvas.canvasx(event.x)
        self.y = self.canvas.canvasy(event.y)
        self.zoom_in = 0
        self.canvas.scan_mark(event.x, event.y)

    def move_to(self, event):
        self.x = self.canvas.canvasx(event.x)
        self.y = self.canvas.canvasy(event.y)
        self.zoom_in = 0
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        
        self.update_image()

    def wheel(self, event):
        maxZX = self.canvas.winfo_width() / self.width
        maxZY = self.canvas.winfo_height() / self.height
        self.max_zoom = max(maxZX, maxZY)

        self.x = self.canvas.canvasx(event.x)
        self.y = self.canvas.canvasy(event.y)

        if event.delta:
            self.zoom_in = event.delta
            
        if self.zoom_in > 0:
            i = min(self.canvas.winfo_width(), self.canvas.winfo_height())
            if i < self.scale: return
            self.p_scale = self.scale
            self.scale *= self.delta
            self.scale = max(self.scale, self.max_zoom)
        if self.zoom_in < 0:
            i = min(self.width, self.height)
            if int(i * self.scale) < 30: return 
            self.p_scale = self.scale
            self.scale /= self.delta
            self.scale = max(self.scale, self.max_zoom) 
        self.update_image()

    def flood_fill(self, x, y):
        cv2.floodFill(self.image_array, None, (x, y), self.hex_to_rgb(self.current_state_color), 
                      loDiff=(0, 0, 0), upDiff=(0, 0, 0))

    def remove_highlight(self, x, y):
        mask = np.zeros((self.image_array.shape[0] + 2, self.image_array.shape[1] + 2), np.uint8)      
        cv2.floodFill(self.original_image_array, mask, (x, y), (255, 255, 255), 
                      loDiff=(0, 0, 0), upDiff=(0, 0, 0), flags=cv2.FLOODFILL_MASK_ONLY) 
        flood_mask = mask[1:-1, 1:-1]
        self.image_array[flood_mask > 0] = self.original_image_array[flood_mask > 0]

    def on_click(self, event):
        if self.image_array is None:
            return

        self.zoom_in = 0
        self.x = self.canvas.canvasx(event.x)
        self.y = self.canvas.canvasy(event.y)
        image_x = int(self.x / self.scale) + self.vec[0]
        image_y = int(self.y / self.scale) + self.vec[1]

        if 0 <= image_x < self.image_array.shape[1] and 0 <= image_y < self.image_array.shape[0]:
            visible_color = self.rgb_to_hex(self.image_array[image_y, image_x])
            for state_id in self.used_state_ids:
                state_color = self.state_colors.get(state_id)
                if state_color is not None and state_color == visible_color:
                    return  

            clicked_color = self.original_image_array[image_y, image_x]
            hex_code = '#{:02x}{:02x}{:02x}'.format(*clicked_color)


            if hex_code in self.highlighted_provinces:
                self.highlighted_provinces.remove(hex_code)
                for key, entry in self.special_assignments.items():
                    if entry is not None:
                        entry_value = entry.get()
                        if entry_value == hex_code:
                            entry.delete(0, tk.END)
                            self.special_assignments[key] = None
                            break
                self.hex_codes.remove(hex_code)
                self.remove_highlight(image_x, image_y)
            elif self.current_assignment:
                for key, entry in self.special_assignments.items():
                    if entry is not None:
                        entry_value = entry.get()
                        if entry_value == hex_code:
                            entry.delete(0, tk.END)
                            self.special_assignments[key] = None
                            break
                self.special_assignments[self.current_assignment].delete(0, tk.END)
                self.special_assignments[self.current_assignment].insert(0, hex_code)
                self.highlighted_provinces.add(hex_code)
                self.current_assignment = None
                self.hex_codes.append(hex_code)
                self.flood_fill(image_x, image_y)
            else:
                self.highlighted_provinces.add(hex_code)
                self.hex_codes.append(hex_code)
                self.flood_fill(image_x, image_y)

            self.update_provinces_text()
            self.update_image()

    def scroll_y(self, *args, **kwargs):
        self.canvas.yview(*args, **kwargs) 
        self.update_image() 

    def scroll_x(self, *args, **kwargs):
        self.canvas.xview(*args, **kwargs) 
        self.update_image() 

    def save_state(self):
        state_name = self.state_name_entry.get().strip()
        if not state_name:
            messagebox.showerror("Error", "Please enter a state name.")
            return

        state_id = self.state_id_entry.get().strip()
        if not state_id.isdigit() or int(state_id) in self.used_state_ids:
            messagebox.showerror("Error", "State ID must be a unique number.")
            return

        arable_land = self.arable_land_entry.get().strip()
        if not arable_land.isdigit():
            messagebox.showerror("Error", "Arable land must be a number.")
            return

        self.all_states.append(self.state_data)
        self.used_state_ids.add(int(state_id))

        self.state_colors[int(state_id)] = self.current_state_color

        self.hex_codes = []
        self.highlighted_provinces = set()

        self.provinces_text.delete('1.0', tk.END)
        self.state_name_entry.delete(0, tk.END)
        self.state_id_entry.delete(0, tk.END)
        self.arable_land_entry.delete(0, tk.END)
        for var in self.subsistence_vars.values():
            var.set(False)
        for var in self.arable_resources_vars.values():
            var.set(False)
        for var, entry in self.capped_resources_vars.values():
            var.set(False)
            entry.delete(0, tk.END)
        for var, entry in self.special_resources_vars.values():
            var.set(False)
            entry.delete(0, tk.END)

        for entry in self.special_assignments.values():
            if entry is not None:
                entry.delete(0, tk.END)

        self.current_state_color = self.generate_random_color()
        self.color_preview.config(bg=self.current_state_color)
        self.current_assignment = None

        self.update_image()
 
    def update_provinces_text(self):
        self.provinces_text.delete('1.0', tk.END)
        state_name = self.state_name_entry.get().strip().replace(' ', '_').upper()
    
        self.state_data = f"STATE_{state_name} = {{\n"
        self.state_data += f"    id = {self.state_id_entry.get()}\n"
        
        checked_subsistence = [label for label, var in self.subsistence_vars.items() if var.get()]
        if checked_subsistence:
            self.state_data += f'    subsistence_building = "{checked_subsistence[0]}"\n'
        else:
            self.state_data += '    subsistence_building = ""\n'
        
        self.state_data += f"    provinces = {{ {' '.join(f'\"{code}\"' for code in self.hex_codes)} }}\n"

        for assignment, entry in self.special_assignments.items():
            if entry is not None: 
                value = entry.get()
                if value:
                    self.state_data += f"    {assignment} = \"{value}\"\n"

        arable_land = self.arable_land_entry.get().strip()
        if arable_land.isdigit():
            self.state_data += f"    arable_land = {arable_land}\n"

        arable_resources = [f'"{res}"' for res, var in self.arable_resources_vars.items() if var.get()]
        if arable_resources:
            self.state_data += f"    arable_resources = {{ {' '.join(arable_resources)} }}\n"

        capped_resources = {res: entry.get() for res, (var, entry) in self.capped_resources_vars.items() if var.get() and entry.get().strip()}
        if capped_resources:
            self.state_data += "    capped_resources = {\n"
            for res, value in capped_resources.items():
                self.state_data += f"        {res} = {value}\n"
            self.state_data += "    }\n"

        for res, (var, entry) in self.special_resources_vars.items():
            if var.get() and entry.get().strip():
                if res == "bg_gold_fields":
                    self.state_data += f"""    resource = {{
        type = "{res}"
        depleted_type = "bg_gold_mining"
        undiscovered_amount = {entry.get()}
    }}\n"""
                else:
                    self.state_data += f"""    resource = {{
        type = "{res}"
        undiscovered_amount = {entry.get()}
    }}\n"""

        self.state_data += "}\n"
        self.provinces_text.insert(tk.END, self.state_data)

    def on_subsistence_change(self):
        checked = [key for key, var in self.subsistence_vars.items() if var.get()]
        if len(checked) > 1:
            for key in checked[1:]:
                self.subsistence_vars[key].set(False)
        self.update_provinces_text()

    def on_change(self, event):
        self.update_provinces_text()

    def create_widgets(self):
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.right_panel = ttk.Frame(main_frame, width=400)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.right_panel.grid_rowconfigure(0, weight=1)
        self.right_panel.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(self.right_panel, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky='nswe')

        self.x_scrollbar = ttk.Scrollbar(self.right_panel, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.x_scrollbar.grid(row=1, column=0, sticky='ew')
        self.y_scrollbar = ttk.Scrollbar(self.right_panel, orient=tk.VERTICAL, command=self.canvas.yview)
        self.y_scrollbar.grid(row=0, column=1, sticky='ns')

        self.canvas.configure(xscrollcommand=self.x_scrollbar.set, yscrollcommand=self.y_scrollbar.set)

        #self.container = self.canvas.create_rectangle(0, 0, 8192, 3616, width=0)
        self.canvas.update()  

        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind('<ButtonPress-3>', self.move_from)
        self.canvas.bind('<B3-Motion>',     self.move_to)
        self.canvas.bind('<MouseWheel>', self.wheel)

        self.left_panel = ttk.Frame(main_frame, width=400)
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y)
        self.left_panel.pack_propagate(False)

        button_frame = ttk.Frame(self.left_panel)
        button_frame.pack(pady=10)
        self.pick_button = ttk.Button(button_frame, text="Pick PNG", command=self.choose_image)
        self.save_button = ttk.Button(button_frame, text="Save State", command=self.save_state)
        self.export_button = ttk.Button(button_frame, text="Export All States", command=self.export_all_states)
        self.pick_button.pack(side=tk.LEFT, padx=5)
        self.save_button.pack(side=tk.LEFT, padx=5)
        self.export_button.pack(side=tk.LEFT, padx=5)

        info_frame = ttk.Frame(self.left_panel)
        info_frame.pack(pady=10, fill=tk.X)

        self.state_id_label = ttk.Label(info_frame, text="State ID:")
        self.state_id_label.grid(row=0, column=0, padx=(10, 5), sticky="w")

        self.state_id_entry = ttk.Entry(info_frame, width=20)
        self.state_id_entry.grid(row=0, column=1, padx=(0, 5), pady=10, sticky="ew")
        self.state_id_entry.bind("<KeyRelease>", self.on_change)

        self.state_id_button = ttk.Button(info_frame, text="Rand", command=self.regen_id)
        self.state_id_button.grid(row=0, column=2, padx=(0, 10), pady=10, sticky="e")

        self.state_name_label = ttk.Label(info_frame, text="State Name:")
        self.state_name_label.grid(row=1, column=0, padx=(10, 5), pady= 10, sticky="w")
        self.state_name_entry = ttk.Entry(info_frame, width=30)
        self.state_name_entry.grid(row=1, column=1, padx=(0, 10), pady= 10, sticky="e")
        self.state_name_entry.bind("<KeyRelease>", self.on_change)


        color_frame = ttk.Frame(self.left_panel)
        color_frame.pack(pady=(10, 0), padx=10, fill=tk.X)

        self.color_preview = tk.Canvas(color_frame, width=47, height=50, bg=self.current_state_color)
        self.color_preview.grid(row = 1,column= 0, padx=50, sticky="e")

        self.subsistence_vars = {
            "building_subsistence_farms": tk.BooleanVar(value=False),
            "building_subsistence_rice_paddies": tk.BooleanVar(value=False),
            "building_subsistence_pastures": tk.BooleanVar(value=False)
        }

        for i, (label, var) in enumerate(self.subsistence_vars.items()):
            cb = ttk.Checkbutton(color_frame, text=label, variable=var, command=self.on_subsistence_change)
            cb.grid(row=i, column=1, sticky="w")

        arab_frame = ttk.Frame(self.left_panel)
        arab_frame.pack(padx=30, fill=tk.X)

        self.arable_land_label = ttk.Label(arab_frame, text="Arable Land:")
        self.arable_land_label.grid(row=0, column=0, padx=(10, 5), sticky="e")
        self.arable_land_entry = ttk.Entry(arab_frame)
        self.arable_land_entry.grid(row=0, column=1, padx=(0, 10), sticky="w")
        self.arable_land_entry.bind("<KeyRelease>", self.on_change)

        self.arable_resources_frame = ttk.Frame(self.left_panel)
        self.arable_resources_frame.pack(pady=(0, 10), padx=10, fill=tk.X)
        self.arable_resources_vars = {}
        arable_resources = [
            "bg_silk_plantations", "bg_opium_plantations", "bg_cotton_plantations",
            "bg_coffee_plantations", "bg_dye_plantations", "bg_sugar_plantations",
            "bg_banana_plantations", "bg_tobacco_plantations", "bg_vineyard_plantations",
            "bg_maize_farms", "bg_rye_farms", "bg_livestock_ranches", "bg_wheat_farms"
        ]
        for i, resource in enumerate(arable_resources):
            var = tk.BooleanVar()
            cb = ttk.Checkbutton(self.arable_resources_frame, text=resource, variable=var, command=self.update_provinces_text)
            cb.grid(row=i // 2, column=i % 2, sticky="w")
            self.arable_resources_vars[resource] = var

        self.resources_frame = ttk.Frame(self.left_panel)
        self.resources_frame.pack(pady=(0, 10), padx=10, fill=tk.X)

        self.capped_resources_vars = {}
        capped_resources = [
            "bg_coal_mining", "bg_iron_mining", "bg_lead_mining", "bg_sulfur_mining",
            "bg_logging", "bg_fishing", "bg_monuments"
        ]
        for i, resource in enumerate(capped_resources):
            var = tk.BooleanVar()
            cb = ttk.Checkbutton(self.resources_frame, text=resource, variable=var, command=self.update_provinces_text)
            cb.grid(row=i, column=0, sticky="w")
            entry = ttk.Entry(self.resources_frame, width=5)
            entry.grid(row=i, column=1, padx=(0, 10))
            entry.bind("<KeyRelease>", self.on_change)
            self.capped_resources_vars[resource] = (var, entry)

        self.special_resources_vars = {}
        special_resources = [
            "bg_oil_extraction",
            "bg_gold_fields",
            "bg_rubber"
        ]
        for i, resource in enumerate(special_resources):
            var = tk.BooleanVar()
            cb = ttk.Checkbutton(self.resources_frame, text=resource, variable=var, command=self.update_provinces_text)
            cb.grid(row=i, column=2, sticky="w")
            entry = ttk.Entry(self.resources_frame, width=5)
            entry.grid(row=i, column=3, padx=(0, 10))
            entry.bind("<KeyRelease>", self.on_change)
            self.special_resources_vars[resource] = (var, entry)

        self.special_assignments_frame = ttk.Frame(self.left_panel)
        self.special_assignments_frame.pack(pady=(0, 10), padx=5, fill=tk.X)

        for i, assignment in enumerate(["city", "farm", "mine", "wood", "port"]):
            btn = ttk.Button(self.special_assignments_frame, text=assignment.capitalize(), command=lambda a=assignment: self.set_current_assignment(a), width=8)
            btn.grid(row=0, column=i, padx=5)
            entry = ttk.Entry(self.special_assignments_frame, width=8)
            entry.grid(row=1, column=i, padx=5, pady=(5, 0))
            self.special_assignments[assignment] = entry


        self.provinces_label = ttk.Label(self.left_panel, text="Current State Configuration:")
        self.provinces_label.pack(pady=(10, 0))

        self.provinces_text = tk.Text(self.left_panel, height=10, wrap=tk.WORD)
        self.provinces_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))


    def export_all_states(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text files", "*.txt")])
        if file_path:
            with open(file_path, 'w') as f:
                for state_data in self.all_states:
                    f.write(state_data + '\n')

    def generate_random_color(self):
        while True:
            color = "#{:06x}".format(random.randint(0, 0xFFFFFF))
            if color not in self.state_colors.values():
                return color

    @staticmethod
    def hex_to_rgb(hex_color):
        return tuple(int(hex_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    
    @staticmethod
    def rgb_to_hex(rgb):
        r, g, b = rgb   
        hex_color = '#{:02x}{:02x}{:02x}'.format(r, g, b)
        
        return hex_color
    
    def regen_id(self):       
        new_id = 1
        while new_id in self.used_state_ids:
            new_id += 1
        
        self.state_id_entry.delete(0, tk.END)
        self.state_id_entry.insert(0, str(new_id))

    def set_current_assignment(self, assignment):
        self.current_assignment = assignment

if __name__ == "__main__":
    root = tk.Tk()
    app = VicStatePainter(root)
    root.mainloop()