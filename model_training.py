# model_training/fine_tune_yolo.py
from ultralytics import YOLO
import torch
from pathlib import Path
import yaml
from torch.utils.data import Dataset, DataLoader
import albumentations as A

class BarbershopPoseDataset(Dataset):
    """Custom dataset for barbershop pose estimation"""
    
    def __init__(self, data_path, split='train', augment=True):
        self.data_path = Path(data_path)
        self.split = split
        self.augment = augment
        
        # Load annotations
        with open(self.data_path / f'{split}_annotations.json', 'r') as f:
            self.annotations = json.load(f)
        
        # Define keypoint connections specific to barbershop
        self.barbershop_connections = [
            (5, 6),   # Shoulder to shoulder
            (5, 7), (7, 9),   # Left arm to wrist
            (6, 8), (8, 10),  # Right arm to wrist
            (5, 11), (6, 12),  # Shoulder to hip
            (11, 12), (11, 13), (13, 15),  # Left leg
            (12, 14), (14, 16)  # Right leg
        ]
        
        # Additional barbershop-specific keypoint pairs
        self.shave_interaction_pairs = [
            (9, 0),   # Left wrist to nose
            (10, 0),  # Right wrist to nose
            (9, 1), (9, 2),  # Wrists to eyes
            (10, 1), (10, 2)
        ]
    
    def __len__(self):
        return len(self.annotations)
    
    def __getitem__(self, idx):
        ann = self.annotations[idx]
        
        # Load image
        image = cv2.imread(str(self.data_path / ann['image_path']))
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Apply augmentations
        if self.augment:
            transform = A.Compose([
                A.RandomRotate90(p=0.5),
                A.HorizontalFlip(p=0.5),
                A.RandomBrightnessContrast(p=0.2),
                A.GaussNoise(p=0.1)
            ], keypoint_params=A.KeypointParams(format='xy'))
            
            transformed = transform(
                image=image,
                keypoints=ann['keypoints']
            )
            
            image = transformed['image']
            keypoints = transformed['keypoints']
        else:
            keypoints = ann['keypoints']
        
        # Convert to tensor
        image = torch.from_numpy(image).permute(2, 0, 1).float() / 255.0
        
        # Create keypoint heatmaps (Gaussian blobs)
        heatmaps = self.create_heatmaps(keypoints, image.shape[1:])
        
        return image, heatmaps, keypoints
    
    def create_heatmaps(self, keypoints, image_size, sigma=3):
        """Create Gaussian heatmaps for each keypoint"""
        h, w = image_size
        num_keypoints = 17  # COCO keypoint format
        heatmaps = np.zeros((num_keypoints, h, w), dtype=np.float32)
        
        for i, (x, y, v) in enumerate(keypoints):
            if v > 0:  # Visible keypoint
                # Create Gaussian
                y_grid, x_grid = np.meshgrid(np.arange(h), np.arange(w), indexing='ij')
                gaussian = np.exp(-((x_grid - x)**2 + (y_grid - y)**2) / (2 * sigma**2))
                heatmaps[i] = gaussian / gaussian.max()
        
        return heatmaps

class FineTuneConfig:
    """Configuration for fine-tuning"""
    
    def __init__(self):
        # Training parameters
        self.epochs = 100
        self.batch_size = 8
        self.learning_rate = 0.001
        self.weight_decay = 0.0005
        self.warmup_epochs = 3
        
        # Model parameters
        self.model_size = 'nano'  # 'nano', 'small', 'medium'
        self.pretrained_weights = 'yolov8n-pose.pt'
        
        # Data parameters
        self.train_data_path = './barbershop_data/train'
        self.val_data_path = './barbershop_data/val'
        self.num_workers = 4
        
        # Loss weights
        self.box_loss_weight = 7.5
        self.cls_loss_weight = 0.5
        self.pose_loss_weight = 1.0
        
    def get_model(self):
        """Get model with appropriate size"""
        models = {
            'nano': YOLO('yolov8n-pose.pt'),
            'small': YOLO('yolov8s-pose.pt'),
            'medium': YOLO('yolov8m-pose.pt')
        }
        return models[self.model_size]

def fine_tune_model(config):
    """Fine-tune YOLOv8-pose on barbershop data"""
    
    # Load pre-trained model
    model = config.get_model()
    
    # Prepare dataset
    train_dataset = BarbershopPoseDataset(
        config.train_data_path,
        split='train',
        augment=True
    )
    
    val_dataset = BarbershopPoseDataset(
        config.val_data_path,
        split='val',
        augment=False
    )
    
    # Training arguments
    args = {
        'epochs': config.epochs,
        'batch': config.batch_size,
        'lr0': config.learning_rate,
        'weight_decay': config.weight_decay,
        'warmup_epochs': config.warmup_epochs,
        'device': 0 if torch.cuda.is_available() else 'cpu',
        'workers': config.num_workers,
        'project': 'barbershop_finetune',
        'name': f'pose_{config.model_size}',
        'exist_ok': True,
        'pretrained': True,
        'optimizer': 'AdamW',
        'cos_lr': True,
        'label_smoothing': 0.1,
        'dropout': 0.2,
        'degrees': 10.0,
        'translate': 0.1,
        'scale': 0.5,
        'flipud': 0.1,
        'fliplr': 0.5,
        'mosaic': 1.0,
        'mixup': 0.1,
        'copy_paste': 0.1
    }
    
    # Train model
    results = model.train(**args)
    
    # Export optimized versions
    model.export(format='onnx')  # ONNX
    model.export(format='tflite')  # TensorFlow Lite for edge
    model.export(format='engine')  # TensorRT for Jetson
    
    # Evaluate on validation set
    metrics = model.val()
    
    print(f"[TRAINING COMPLETE]")
    print(f"  - mAP: {metrics.box.map:.3f}")
    print(f"  - Pose mAP: {metrics.pose.map:.3f}")
    print(f"  - Best model saved to: barbershop_finetune/pose_{config.model_size}/weights/best.pt")
    
    return model, metrics

def augment_training_data(video_paths, output_dir):
    """Generate augmented training data from real videos"""
    
    augmentations = A.Compose([
        A.RandomRotate90(p=0.3),
        A.HorizontalFlip(p=0.5),
        A.RandomBrightnessContrast(p=0.3),
        A.GaussNoise(p=0.2),
        A.Blur(blur_limit=3, p=0.1),
        A.CLAHE(p=0.1),
        A.RandomGamma(p=0.2),
        A.RGBShift(p=0.2)
    ])
    
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    frame_count = 0
    for video_path in video_paths:
        cap = cv2.VideoCapture(video_path)
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Save original
            cv2.imwrite(str(output_dir / f'frame_{frame_count:06d}_orig.jpg'), frame)
            
            # Generate augmented versions
            for i in range(3):  # 3 augmentations per frame
                augmented = augmentations(image=frame)['image']
                cv2.imwrite(str(output_dir / f'frame_{frame_count:06d}_aug_{i}.jpg'), augmented)
            
            frame_count += 1
            
            if frame_count % 1000 == 0:
                print(f"Generated {frame_count} frames")
        
        cap.release()
    
    print(f"Total frames generated: {frame_count}")