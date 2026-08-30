import torch
import cv2
import numpy as np
from model import SurveillanceAnomalyDetector
import torchvision.transforms as transforms
from PIL import Image

def debug():
    model = SurveillanceAnomalyDetector(num_classes=14, pretrained=False)
    model.load_state_dict(torch.load('model.pth'))
    model.eval()
    
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    
    # Normal frame
    img_normal = np.zeros((224, 224, 3), dtype=np.uint8)
    cv2.circle(img_normal, (100, 130), 15, (200, 200, 200), -1)
    t_normal = transform(Image.fromarray(img_normal)).unsqueeze(0)
    
    # Fighting frame
    img_fighting = np.zeros((224, 224, 3), dtype=np.uint8)
    cv2.circle(img_fighting, (105, 120), 18, (50, 50, 220), -1)
    cv2.circle(img_fighting, (115, 125), 18, (220, 50, 50), -1)
    t_fighting = transform(Image.fromarray(img_fighting)).unsqueeze(0)
    
    with torch.no_grad():
        anom_n, cat_n = model(t_normal)
        anom_f, cat_f = model(t_fighting)
        
    print("Normal outputs:")
    print("  Anomaly logit:", anom_n.item())
    print("  Category logits sum:", cat_n.sum().item())
    print("  Category probabilities:", torch.softmax(cat_n, dim=1).squeeze(0)[:4].tolist())
    
    print("Fighting outputs:")
    print("  Anomaly logit:", anom_f.item())
    print("  Category logits sum:", cat_f.sum().item())
    print("  Category probabilities:", torch.softmax(cat_f, dim=1).squeeze(0)[:4].tolist())

if __name__ == '__main__':
    debug()
