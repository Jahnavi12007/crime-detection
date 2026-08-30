import torch
import torch.nn as nn
import torchvision.models as models

class SurveillanceAnomalyDetector(nn.Module):
    def __init__(self, num_classes=14, pretrained=True):
        super(SurveillanceAnomalyDetector, self).__init__()
        # Load MobileNetV2 as feature extractor
        if pretrained:
            weights = models.MobileNet_V2_Weights.DEFAULT
            self.backbone = models.mobilenet_v2(weights=weights)
            # Freeze backbone features
            for param in self.backbone.parameters():
                param.requires_grad = False
        else:
            self.backbone = models.mobilenet_v2(weights=None)

            
        # Extract features (1280 dimensional from mobile net bottleneck)
        # Replacing classifier with identity to keep the feature map output
        self.feature_dim = self.backbone.last_channel # 1280
        self.backbone.classifier = nn.Identity()
        
        # Binary anomaly head (0 = Normal, 1 = Anomaly/Crime/Violence)
        self.anomaly_head = nn.Sequential(
            nn.Linear(self.feature_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.4),
            nn.Linear(256, 1) # Output raw logit for sigmoid
        )
        
        # Multiclass category head (Normal, Fighting, Burglary, etc.)
        self.category_head = nn.Sequential(
            nn.Linear(self.feature_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.4),
            nn.Linear(256, num_classes) # Raw logits for cross-entropy
        )

    def forward(self, x):
        # Input shape: (Batch, Channels, Height, Width) -> e.g. (B, 3, 224, 224)
        features = self.backbone(x) # Shape: (B, 1280)
        
        anomaly_logit = self.anomaly_head(features) # Shape: (B, 1)
        category_logit = self.category_head(features) # Shape: (B, num_classes)
        
        return anomaly_logit, category_logit

class SurveillanceTemporalDetector(nn.Module):
    def __init__(self, num_classes=14, pretrained=True, sequence_length=16):
        super(SurveillanceTemporalDetector, self).__init__()
        # Load MobileNetV2 features
        if pretrained:
            weights = models.MobileNet_V2_Weights.DEFAULT
            self.backbone = models.mobilenet_v2(weights=weights)
        else:
            self.backbone = models.mobilenet_v2(weights=None)
            
        self.feature_dim = self.backbone.last_channel # 1280
        self.backbone.classifier = nn.Identity()
        
        # Freeze backbone features
        for param in self.backbone.parameters():
            param.requires_grad = False
            
        # Lightweight temporal head (GRU)
        # Input shape to GRU: (Batch, Sequence_length, Feature_dim)
        self.gru = nn.GRU(
            input_size=self.feature_dim,
            hidden_size=128,
            num_layers=1,
            batch_first=True,
            bidirectional=False
        )
        
        # Binary anomaly head
        self.anomaly_head = nn.Sequential(
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.4),
            nn.Linear(64, 1) # logit for sigmoid
        )
        
        # Multiclass category head
        self.category_head = nn.Sequential(
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.4),
            nn.Linear(64, num_classes) # logits for cross-entropy
        )

    def forward(self, x):
        # Input shape: (Batch, Sequence_length, 3, 224, 224) OR (Batch, Sequence_length, Feature_dim)
        if len(x.shape) == 5:
            b, t, c, h, w = x.shape
            # Flatten batch and temporal dimensions to pass through 2D CNN
            x_flat = x.view(b * t, c, h, w)
            features_flat = self.backbone(x_flat) # Shape: (B*T, 1280)
            features = features_flat.view(b, t, self.feature_dim) # Shape: (B, T, 1280)
        else:
            features = x # Shape: (B, T, Feature_dim)
            
        # Run temporal GRU
        gru_out, _ = self.gru(features) # Shape: (B, T, 128)
        
        # We classify based on the final time-step of the window
        last_step_out = gru_out[:, -1, :] # Shape: (B, 128)
        
        anomaly_logit = self.anomaly_head(last_step_out) # Shape: (B, 1)
        category_logit = self.category_head(last_step_out) # Shape: (B, num_classes)
        
        return anomaly_logit, category_logit

