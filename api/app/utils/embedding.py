from transformers import AutoTokenizer, AutoModel
import torch
import time 


class EmbeddingService:
    def __init__(self):
        self.tokenizer = None 
        self.model = None 

    def load_model(self):
        print("===== 모델 로딩 중 ...====")
        self.tokenizer = AutoTokenizer.from_pretrained("klue/bert-base")
        self.model = AutoModel.from_pretrained("klue/bert-base")

        print("===== 모델 로딩 완료 ! =====")

    def get_embedding(self, text):
        if self.model is None or self.tokenizer is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        inputs = self.tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512)

        with torch.no_grad():
            output = self.model(**inputs)

        embedding = output.last_hidden_state[:, 0, :].squeeze().numpy()

        return embedding.tolist()

embedding_service = EmbeddingService()

def get_embedding(text):
    return embedding_service.get_embedding(text)