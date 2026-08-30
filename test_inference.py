import cv2
import numpy as np
from inference import SurveillanceInference

def test_inference():
    print("Testing inference engine...")
    try:
        engine = SurveillanceInference(model_path='model.pth')
        # Create a dummy image (black canvas with a red circle)
        img = np.zeros((224, 224, 3), dtype=np.uint8)
        cv2.circle(img, (112, 112), 30, (0, 0, 255), -1)
        
        res = engine.predict_frame(img)
        print("Prediction Result:")
        print(f"  Anomaly Score: {res['anomaly_score']:.4f}")
        print(f"  Is Anomaly: {res['is_anomaly']}")
        print(f"  Category: {res['category']}")
        print(f"  Top probabilities: {list(res['category_probabilities'].items())[:3]}")
        
        assert 'anomaly_score' in res
        assert 'category' in res
        print("Inference Engine test PASSED!")
    except Exception as e:
        print(f"Inference Engine test FAILED: {e}")
        raise e

if __name__ == '__main__':
    test_inference()
