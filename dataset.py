import os
import cv2
import numpy as np
import torch
from torch.utils.data import Dataset
from PIL import Image
import torchvision.transforms as transforms

# Define categories
CATEGORIES = [
    'Normal', 'Abuse', 'Arrest', 'Arson', 'Assault', 
    'Burglary', 'Explosion', 'Fighting', 'RoadAccident', 
    'Robbery', 'Shooting', 'Shoplifting', 'Stealing', 'Vandalism',
    'Weapons', 'Falls', 'Panic', 'Trespass', 'Abandoned'
]

# Map category name to index
CATEGORY_TO_IDX = {cat: i for i, cat in enumerate(CATEGORIES)}
IDX_TO_CATEGORY = {i: cat for i, cat in enumerate(CATEGORIES)}

class SurveillanceDataset(Dataset):
    def __init__(self, data_dir, transform=None):
        self.data_dir = data_dir
        self.transform = transform
        self.samples = []
        
        # Load directories
        if os.path.exists(data_dir):
            for class_name in os.listdir(data_dir):
                class_path = os.path.join(data_dir, class_name)
                if os.path.isdir(class_path):
                    # Check if class name is in our categories list
                    if class_name in CATEGORY_TO_IDX:
                        class_idx = CATEGORY_TO_IDX[class_name]
                        anomaly_label = 0.0 if class_name == 'Normal' else 1.0
                        for img_name in os.listdir(class_path):
                            if img_name.lower().endswith(('.png', '.jpg', '.jpeg')):
                                self.samples.append({
                                    'path': os.path.join(class_path, img_name),
                                    'category': class_idx,
                                    'anomaly': anomaly_label
                                })
                                
    def __len__(self):
        return len(self.samples)
        
    def __getitem__(self, idx):
        sample = self.samples[idx]
        img_path = sample['path']
        
        # Load image
        img = Image.open(img_path).convert('RGB')
        
        if self.transform:
            img = self.transform(img)
        else:
            # Default transform if not specified
            default_t = transforms.Compose([
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
            ])
            img = default_t(img)
            
        return img, torch.tensor(sample['anomaly'], dtype=torch.float32), torch.tensor(sample['category'], dtype=torch.long)

def get_transforms():
    train_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(15),
        transforms.ColorJitter(brightness=0.2, contrast=0.2),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    
    val_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    
    return train_transform, val_transform

def generate_synthetic_data(output_dir, num_samples=190):
    """
    Generates synthetic frames for all 19 classes in CATEGORIES
    to verify pipeline execution and train/fine-tune the classification model.
    """
    print(f"Generating synthetic surveillance dataset at {output_dir}...")
    np.random.seed(42)
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Ensure at least 5 samples per class
    samples_per_class = max(5, num_samples // len(CATEGORIES))
    
    for class_name in CATEGORIES:
        class_path = os.path.join(output_dir, class_name)
        os.makedirs(class_path, exist_ok=True)
        
        for i in range(samples_per_class):
            # Create a 224x224 grey background canvas
            img = np.zeros((224, 224, 3), dtype=np.uint8)
            # Add some constant "surveillance background" grid lines
            cv2.line(img, (0, 40), (224, 40), (40, 40, 40), 1)
            cv2.line(img, (0, 180), (224, 180), (40, 40, 40), 1)
            cv2.putText(img, f"CAM-01 {class_name}", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 100, 100), 1)
            
            if class_name == 'Normal':
                # Normal behavior: slow moving circle, linear motion
                cx = int(80 + (i * 10) % 80)
                cy = 130
                cv2.circle(img, (cx, cy), 15, (200, 200, 200), -1) # Head
                cv2.line(img, (cx, cy + 15), (cx, cy + 50), (200, 200, 200), 3) # Body
                cv2.line(img, (cx, cy + 50), (cx - 10, cy + 80), (200, 200, 200), 2) # Leg 1
                cv2.line(img, (cx, cy + 50), (cx + 10, cy + 80), (200, 200, 200), 2) # Leg 2
            elif class_name in ['Fighting', 'Assault']:
                # Fighting: chaotic overlapping red/blue shapes
                shift = int(np.random.randint(-15, 15))
                cv2.circle(img, (100 + shift, 120), 18, (50, 50, 220), -1)
                cv2.circle(img, (120 - shift, 125), 18, (220, 50, 50), -1)
                # impact lines
                for _ in range(3):
                    x1 = int(np.random.randint(70, 150))
                    y1 = int(np.random.randint(90, 160))
                    cv2.line(img, (x1, y1), (x1 + int(np.random.randint(-15, 15)), y1 + int(np.random.randint(-15, 15))), (255, 255, 0), 2)
            elif class_name == 'Weapons':
                # Weapons: person with highlighted red bounding box around a weapon shape
                cv2.circle(img, (110, 120), 18, (200, 200, 200), -1)
                # Bounding box
                cv2.rectangle(img, (100, 100), (145, 150), (0, 0, 255), 2)
                # Gun outline
                cv2.rectangle(img, (115, 125), (135, 135), (50, 50, 50), -1)
                cv2.line(img, (120, 135), (120, 142), (50, 50, 50), 3)
            elif class_name == 'Falls':
                # Falls: collapsed flat shape on the ground
                cv2.ellipse(img, (112, 185), (35, 12), 0, 0, 360, (200, 50, 50), -1)
                cv2.putText(img, "HEIGHT CRITICAL", (60, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 165, 255), 1)
            elif class_name == 'Panic':
                # Panic: multiple fast-moving random dots
                for j in range(8):
                    rx = int(40 + np.random.randint(0, 140))
                    ry = int(50 + np.random.randint(0, 120))
                    cv2.circle(img, (rx, ry), 8, (0, 255, 255), -1)
            elif class_name == 'Trespass' or class_name == 'Burglary':
                # Trespass/Burglary: restricted area line with actor encroaching
                cv2.rectangle(img, (150, 80), (200, 180), (180, 180, 180), 2)
                cv2.circle(img, (140, 140), 15, (50, 200, 50), -1)
                cv2.line(img, (130, 60), (130, 200), (0, 0, 255), 2) # Alarm boundary line
            elif class_name == 'Abandoned':
                # Abandoned Object: bounding box around a small package block left alone
                cv2.rectangle(img, (112, 160), (130, 178), (255, 100, 50), -1)
                cv2.rectangle(img, (98, 145), (144, 192), (255, 0, 0), 1)
            else:
                # Default placeholder anomaly for other classes
                cv2.circle(img, (112, 120), 20, (0, 0, 255), -1)
                cv2.line(img, (112, 120), (112 + int(np.random.randint(-15,15)), 120 + int(np.random.randint(-15,15))), (255,255,255), 2)
                
            # Save image
            img_filename = f"frame_{i:04d}.png"
            cv2.imwrite(os.path.join(class_path, img_filename), img)
            
    print(f"Generated {num_samples} synthetic images across {len(CATEGORIES)} classes successfully.")
