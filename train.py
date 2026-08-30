import os
import argparse
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, random_split, Dataset as TorchDataset
import torch.optim as optim
from dataset import SurveillanceDataset, get_transforms, generate_synthetic_data, CATEGORIES
from model import SurveillanceAnomalyDetector, SurveillanceTemporalDetector

class SequenceDatasetWrapper(TorchDataset):
    def __init__(self, dataset, sequence_length=16):
        self.dataset = dataset
        self.sequence_length = sequence_length
        
    def __len__(self):
        return len(self.dataset)
        
    def __getitem__(self, idx):
        img, anomaly, category = self.dataset[idx]
        # Duplicate the single frame to form a sequence of shape (Sequence_length, 3, 224, 224)
        seq_img = img.unsqueeze(0).repeat(self.sequence_length, 1, 1, 1)
        return seq_img, anomaly, category

def train_model(args):
    # Set device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    
    # Check if data directory exists or is empty
    data_dir = args.data_dir
    is_empty = True
    if os.path.exists(data_dir):
        # Check if contains subdirectories
        subdirs = [d for d in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, d))]
        if len(subdirs) > 0:
            is_empty = False
            
    if is_empty or args.generate_synthetic:
        os.makedirs(data_dir, exist_ok=True)
        generate_synthetic_data(data_dir, num_samples=args.num_samples)
        
    # Get transforms
    train_transform, val_transform = get_transforms()
    
    # Load dataset
    full_dataset = SurveillanceDataset(data_dir, transform=train_transform)
    
    if len(full_dataset) == 0:
        print("Error: No data samples found to train on. Exiting.")
        return
        
    # Split train/val
    train_size = int(0.8 * len(full_dataset))
    val_size = len(full_dataset) - train_size
    train_dataset, val_dataset = random_split(
        full_dataset, [train_size, val_size], 
        generator=torch.Generator().manual_seed(42)
    )
    
    # Wrap datasets to output sequence shapes for GRU model
    train_dataset = SequenceDatasetWrapper(train_dataset, sequence_length=16)
    val_dataset = SequenceDatasetWrapper(val_dataset, sequence_length=16)
    
    # Create dataloaders
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False, num_workers=0)
    
    print(f"Dataset summary:")
    print(f"  Total samples: {len(full_dataset)}")
    print(f"  Training samples: {len(train_dataset)}")
    print(f"  Validation samples: {len(val_dataset)}")
    print(f"  Number of classes: {len(CATEGORIES)}")
    
    # Instantiate model
    print("Initializing Surveillance Temporal Detector model...")
    # Set pretrained=False if we want to train fast on CPU from scratch,
    # or pretrained=True to use MobileNetV2 features.
    model = SurveillanceTemporalDetector(num_classes=len(CATEGORIES), pretrained=args.pretrained)

    model = model.to(device)
    
    # Losses
    anomaly_criterion = nn.BCEWithLogitsLoss()
    category_criterion = nn.CrossEntropyLoss()
    
    # Optimizer
    optimizer = optim.Adam(model.parameters(), lr=args.lr, weight_decay=1e-4)
    
    best_val_loss = float('inf')
    
    # Training Loop
    print("Starting training...")
    for epoch in range(args.epochs):
        model.train()
        running_loss = 0.0
        running_anomaly_acc = 0.0
        running_category_acc = 0.0
        
        for batch_idx, (imgs, anomaly_labels, category_labels) in enumerate(train_loader):
            imgs = imgs.to(device)
            anomaly_labels = anomaly_labels.to(device).unsqueeze(1) # Shape: (B, 1)
            category_labels = category_labels.to(device) # Shape: (B)
            
            optimizer.zero_grad()
            
            # Forward pass
            anomaly_logits, category_logits = model(imgs)
            
            # Compute losses
            loss_anomaly = anomaly_criterion(anomaly_logits, anomaly_labels)
            loss_category = category_criterion(category_logits, category_labels)
            
            # Combined loss
            total_loss = loss_anomaly + loss_category
            
            # Backward pass
            total_loss.backward()
            optimizer.step()
            
            # Metrics
            running_loss += total_loss.item() * imgs.size(0)
            
            # Anomaly accuracy
            anomaly_preds = (torch.sigmoid(anomaly_logits) > 0.5).float()
            running_anomaly_acc += (anomaly_preds == anomaly_labels).sum().item()
            
            # Category accuracy
            category_preds = torch.argmax(category_logits, dim=1)
            running_category_acc += (category_preds == category_labels).sum().item()
            
        epoch_loss = running_loss / len(train_dataset)
        epoch_anomaly_acc = running_anomaly_acc / len(train_dataset) * 100
        epoch_category_acc = running_category_acc / len(train_dataset) * 100
        
        # Validation Loop
        model.eval()
        val_loss = 0.0
        val_anomaly_acc = 0.0
        val_category_acc = 0.0
        
        with torch.no_grad():
            for imgs, anomaly_labels, category_labels in val_loader:
                imgs = imgs.to(device)
                anomaly_labels = anomaly_labels.to(device).unsqueeze(1)
                category_labels = category_labels.to(device)
                
                anomaly_logits, category_logits = model(imgs)
                
                loss_anomaly = anomaly_criterion(anomaly_logits, anomaly_labels)
                loss_category = category_criterion(category_logits, category_labels)
                total_loss = loss_anomaly + loss_category
                
                val_loss += total_loss.item() * imgs.size(0)
                
                anomaly_preds = (torch.sigmoid(anomaly_logits) > 0.5).float()
                val_anomaly_acc += (anomaly_preds == anomaly_labels).sum().item()
                
                category_preds = torch.argmax(category_logits, dim=1)
                val_category_acc += (category_preds == category_labels).sum().item()
                
        epoch_val_loss = val_loss / len(val_dataset)
        epoch_val_anomaly_acc = val_anomaly_acc / len(val_dataset) * 100
        epoch_val_category_acc = val_category_acc / len(val_dataset) * 100
        
        print(f"Epoch [{epoch+1}/{args.epochs}]")
        print(f"  Train -> Loss: {epoch_loss:.4f} | Anomaly Acc: {epoch_anomaly_acc:.2f}% | Category Acc: {epoch_category_acc:.2f}%")
        print(f"  Val   -> Loss: {epoch_val_loss:.4f} | Anomaly Acc: {epoch_val_anomaly_acc:.2f}% | Category Acc: {epoch_val_category_acc:.2f}%")
        
        # Save best model
        if epoch_val_loss < best_val_loss:
            best_val_loss = epoch_val_loss
            torch.save(model.state_dict(), args.model_path)
            print(f"  --> Saved new best model to {args.model_path}")
            
    print("Training completed successfully!")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Train Surveillance Anomaly Detector model')
    parser.add_argument('--data_dir', type=str, default='data', help='Path to dataset directory')
    parser.add_argument('--model_path', type=str, default='model.pth', help='Path to save model weights')
    parser.add_argument('--epochs', type=str, default='5', help='Number of epochs (will be cast to int)')
    parser.add_argument('--batch_size', type=str, default='16', help='Batch size (will be cast to int)')
    parser.add_argument('--lr', type=float, default=0.001, help='Learning rate')
    parser.add_argument('--num_samples', type=str, default='120', help='Number of synthetic samples to generate')
    parser.add_argument('--generate_synthetic', action='store_true', help='Force generation of synthetic dataset')
    parser.add_argument('--pretrained', action='store_true', default=False, help='Use pre-trained MobileNetV2 backbone')
    
    args = parser.parse_args()
    
    # Cast variables from string if they are parsed as such
    args.epochs = int(args.epochs)
    args.batch_size = int(args.batch_size)
    args.num_samples = int(args.num_samples)
    
    train_model(args)
