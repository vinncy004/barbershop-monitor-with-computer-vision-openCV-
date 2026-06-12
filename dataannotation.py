# model_training/annotation_tool.py
import cv2
import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk

class BarbershopAnnotationTool:
    """Interactive annotation tool for barbershop pose data"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Barbershop Pose Annotation Tool")
        self.root.geometry("1200x800")
        
        self.images = []
        self.current_idx = 0
        self.annotations = []
        
        # Keypoint names
        self.keypoint_names = [
            'nose', 'left_eye', 'right_eye', 'left_ear', 'right_ear',
            'left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow',
            'left_wrist', 'right_wrist', 'left_hip', 'right_hip',
            'left_knee', 'right_knee', 'left_ankle', 'right_ankle'
        ]
        
        self.setup_ui()
        self.load_images()
        
    def setup_ui(self):
        """Setup annotation interface"""
        # Canvas for image display
        self.canvas = tk.Canvas(self.root, width=800, height=600, bg='gray')
        self.canvas.pack(side=tk.LEFT, padx=10, pady=10)
        self.canvas.bind('<Button-1>', self.on_click)
        
        # Control panel
        control_frame = tk.Frame(self.root)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)
        
        # Keypoint selector
        tk.Label(control_frame, text="Current Keypoint:").pack()
        self.keypoint_var = tk.StringVar(value='nose')
        self.keypoint_menu = tk.OptionMenu(control_frame, self.keypoint_var, *self.keypoint_names)
        self.keypoint_menu.pack(pady=5)
        
        # Navigation buttons
        tk.Button(control_frame, text="Previous", command=self.prev_image).pack(pady=5)
        tk.Button(control_frame, text="Next", command=self.next_image).pack(pady=5)
        tk.Button(control_frame, text="Save Annotation", command=self.save_annotation).pack(pady=5)
        tk.Button(control_frame, text="Skip Image", command=self.skip_image).pack(pady=5)
        
        # Status labels
        self.status_label = tk.Label(control_frame, text="Ready")
        self.status_label.pack(pady=10)
        
        # Progress bar
        self.progress = tk.ttk.Progressbar(control_frame, length=200, mode='determinate')
        self.progress.pack(pady=10)
        
        # Instructions
        instructions = """
        Instructions:
        1. Select keypoint from dropdown
        2. Click on image to place keypoint
        3. Right-click to remove keypoint
        4. Save when all keypoints are marked
        """
        tk.Label(control_frame, text=instructions, justify=tk.LEFT, font=('Arial', 10)).pack(pady=20)
    
    def load_images(self):
        """Load images from directory"""
        folder = filedialog.askdirectory(title="Select image folder")
        if folder:
            self.image_paths = list(Path(folder).glob('*.jpg')) + list(Path(folder).glob('*.png'))
            self.annotations = [None] * len(self.image_paths)
            self.current_keypoints = [{} for _ in range(len(self.image_paths))]
            self.load_image()
    
    def load_image(self):
        """Load current image"""
        if 0 <= self.current_idx < len(self.image_paths):
            image_path = self.image_paths[self.current_idx]
            self.image = cv2.imread(str(image_path))
            self.image_rgb = cv2.cvtColor(self.image, cv2.COLOR_BGR2RGB)
            self.image_pil = Image.fromarray(self.image_rgb)
            
            # Resize to fit canvas
            self.image_pil.thumbnail((800, 600))
            self.photo = ImageTk.PhotoImage(self.image_pil)
            self.canvas.create_image(400, 300, image=self.photo)
            
            # Draw existing annotations
            self.draw_keypoints()
            
            # Update progress
            annotated = sum(1 for a in self.annotations if a is not None)
            self.progress['value'] = (annotated / len(self.image_paths)) * 100
            self.status_label.config(text=f"Image {self.current_idx + 1}/{len(self.image_paths)}")
    
    def draw_keypoints(self):
        """Draw existing keypoints on canvas"""
        keypoints = self.current_keypoints[self.current_idx]
        for name, (x, y) in keypoints.items():
            # Draw circle
            self.canvas.create_oval(x-3, y-3, x+3, y+3, fill='red', tags='keypoint')
            # Draw label
            self.canvas.create_text(x+10, y-10, text=name, fill='yellow', tags='keypoint')
    
    def on_click(self, event):
        """Handle mouse click for keypoint placement"""
        # Get click coordinates relative to image
        x, y = event.x, event.y
        
        # Get current keypoint name
        keypoint_name = self.keypoint_var.get()
        
        # Store keypoint
        self.current_keypoints[self.current_idx][keypoint_name] = (x, y)
        
        # Redraw
        self.canvas.delete('keypoint')
        self.draw_keypoints()
        
        self.status_label.config(text=f"Placed {keypoint_name} at ({x}, {y})")
    
    def save_annotation(self):
        """Save current annotations in COCO format"""
        keypoints = self.current_keypoints[self.current_idx]
        
        # Convert to COCO format
        coco_keypoints = []
        for name in self.keypoint_names:
            if name in keypoints:
                x, y = keypoints[name]
                coco_keypoints.extend([x, y, 2])  # 2 = visible
            else:
                coco_keypoints.extend([0, 0, 0])  # 0 = not labeled
        
        annotation = {
            'image_path': str(self.image_paths[self.current_idx]),
            'keypoints': coco_keypoints,
            'num_keypoints': len(keypoints),
            'image_size': self.image.shape[:2],
            'annotator': 'human'
        }
        
        self.annotations[self.current_idx] = annotation
        self.status_label.config(text=f"Saved annotation for image {self.current_idx + 1}")
        
        # Auto-advance
        self.next_image()
    
    def skip_image(self):
        """Skip current image"""
        self.status_label.config(text=f"Skipped image {self.current_idx + 1}")
        self.next_image()
    
    def prev_image(self):
        """Go to previous image"""
        if self.current_idx > 0:
            self.current_idx -= 1
            self.load_image()
    
    def next_image(self):
        """Go to next image"""
        if self.current_idx < len(self.image_paths) - 1:
            self.current_idx += 1
            self.load_image()
        else:
            # Save all annotations
            self.export_annotations()
            messagebox.showinfo("Complete", "All images annotated!")
    
    def export_annotations(self):
        """Export all annotations to JSON"""
        output_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")]
        )
        
        if output_path:
            # Split into train/val
            split_idx = int(len(self.annotations) * 0.8)
            
            train_data = [a for a in self.annotations[:split_idx] if a is not None]
            val_data = [a for a in self.annotations[split_idx:] if a is not None]
            
            with open(output_path.replace('.json', '_train.json'), 'w') as f:
                json.dump(train_data, f, indent=2)
            
            with open(output_path.replace('.json', '_val.json'), 'w') as f:
                json.dump(val_data, f, indent=2)
            
            print(f"Exported {len(train_data)} training and {len(val_data)} validation annotations")
    
    def run(self):
        """Run the annotation tool"""
        self.root.mainloop()

if __name__ == "__main__":
    tool = BarbershopAnnotationTool()
    tool.run()