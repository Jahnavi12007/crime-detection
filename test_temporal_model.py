import torch
import sys
from model import SurveillanceTemporalDetector

def test_compilation():
    print("Testing SurveillanceTemporalDetector compilation...")
    try:
        # Create temporal model with 19 classes
        model = SurveillanceTemporalDetector(num_classes=19, pretrained=False)
        print("  Model created successfully!")
        
        # Test Case 1: Sequence of Raw Images
        # Shape: (Batch=2, Seq_len=16, Channels=3, Height=224, Width=224)
        print("  Test Case 1: Sequence of Raw Images...")
        dummy_images = torch.randn(2, 16, 3, 224, 224)
        anomaly_logit, category_logit = model(dummy_images)
        
        print(f"    Anomaly logit shape: {anomaly_logit.shape} (Expected: torch.Size([2, 1]))")
        print(f"    Category logit shape: {category_logit.shape} (Expected: torch.Size([2, 19]))")
        assert anomaly_logit.shape == (2, 1)
        assert category_logit.shape == (2, 19)
        print("    Test Case 1: PASSED!")
        
        # Test Case 2: Sequence of Pre-extracted Features
        # Shape: (Batch=4, Seq_len=16, Feature_dim=1280)
        print("  Test Case 2: Sequence of Pre-extracted Features...")
        dummy_features = torch.randn(4, 16, 1280)
        anomaly_logit, category_logit = model(dummy_features)
        
        print(f"    Anomaly logit shape: {anomaly_logit.shape} (Expected: torch.Size([4, 1]))")
        print(f"    Category logit shape: {category_logit.shape} (Expected: torch.Size([4, 19]))")
        assert anomaly_logit.shape == (4, 1)
        assert category_logit.shape == (4, 19)
        print("    Test Case 2: PASSED!")
        
        print("Model architecture verification completed successfully!")
        return True
    except Exception as e:
        print(f"Model architecture verification FAILED: {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    success = test_compilation()
    sys.exit(0 if success else 1)
