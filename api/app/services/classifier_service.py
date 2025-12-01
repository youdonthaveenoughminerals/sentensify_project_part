import os
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import json
from typing import Dict

class ClassifierService:
    def __init__(self, model_dir: str = "./data/models/kobert-classifier"):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model_dir = model_dir
        self.model = None
        self.tokenizer = None
        self.id2label = None
        
        # Load on init
        self._load_model()

    def _load_model(self):
        print(f"[Classifier] Loading model from {self.model_dir}...")
        if not os.path.exists(self.model_dir):
            print(f"[Classifier] ⚠️ Warning: Model directory not found at {self.model_dir}. P_rule will be 0.")
            return

        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_dir)
            self.model = AutoModelForSequenceClassification.from_pretrained(self.model_dir)
            self.model.to(self.device)
            self.model.eval()
            
            label_map_path = os.path.join(self.model_dir, 'label_map.json')
            if os.path.exists(label_map_path):
                with open(label_map_path, 'r', encoding='utf-8') as f:
                    label_map = json.load(f)
                    self.id2label = {int(k): v for k, v in label_map.items()}
            print("[Classifier] Model loaded successfully!")
        except Exception as e:
            print(f"[Classifier] ❌ Failed to load model: {e}")
            self.model = None

    def predict_p_rule(self, text: str) -> Dict[str, float]:
        """
        Returns raw probability distribution (P_rule) for the input text.
        Example: {"email": 0.8, "report": 0.1, ...}
        """
        if not self.model or not self.tokenizer:
            return {}

        try:
            inputs = self.tokenizer(
                text, 
                return_tensors="pt", 
                truncation=True, 
                max_length=256, 
                padding="max_length"
            )
            input_ids = inputs['input_ids'].to(self.device)
            attention_mask = inputs['attention_mask'].to(self.device)

            with torch.no_grad():
                outputs = self.model(input_ids, attention_mask=attention_mask)
                probs = F.softmax(outputs.logits, dim=1)
                
            # Convert to dict
            prob_vector = probs[0].cpu().numpy().tolist()
            result = {}
            
            # Standardize Keys (Korean -> English)
            CATEGORY_MAP = {
                "논문": "thesis",
                "보고서": "report",
                "기사": "article",
                "마케팅": "marketing",
                "상담": "customer_service"
                # "이메일" is removed
            }

            if self.id2label:
                for idx, score in enumerate(prob_vector):
                    label_ko = self.id2label.get(idx, str(idx))
                    if label_ko in CATEGORY_MAP:
                        label_en = CATEGORY_MAP[label_ko]
                        result[label_en] = score
            else:
                # Fallback if no label map
                for idx, score in enumerate(prob_vector):
                    result[str(idx)] = score
                    
            return result
        except Exception as e:
            print(f"[Classifier] Prediction error: {e}")
            return {}
