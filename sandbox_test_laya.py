
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def run_poc():
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except Exception as e:
        logger.error(f"Environment Error: Failed to import torch or transformers. This usually indicates missing Visual C++ Redistributables (e.g. c10.dll cannot be loaded). Exception: {e}")
        logger.info("Exiting POC since the required environment dependencies are not functional.")
        return

    MODEL_NAME = "convaiinnovations/laya"
    
    try:
        logger.info(f"Attempting to load {MODEL_NAME}...")
        # Note: convaiinnovations/laya uses a non-standard directory structure.
        # The tokenizer is in the 'tokenizer/' subfolder, and the config is in 'encoder/'.
        # However, model.safetensors is at the root, making standard from_pretrained tricky
        # without a custom model loading script. We attempt to load it with explicit subfolders.
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, subfolder="tokenizer")
        # For the model, we attempt to load it, but it may fail if it expects the config and weights in the same dir.
        model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=2, subfolder="encoder")
        model.eval()
    except Exception as e:
        logger.warning(f"Failed to load {MODEL_NAME} natively due to architecture/structure mismatches. Exception: {e}")
        logger.info("Falling back to generic distilbert-base-uncased to mock non-autoregressive decision flow.")
        MODEL_NAME = "distilbert-base-uncased"
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        # 2 labels: 0 = No Buy, 1 = Buy
        model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=2)
        model.eval()

    def decide_trade(market_data: dict) -> dict:
        """
        Takes market data and returns a structured decision
        using a single forward pass (System 1 / non-autoregressive).
        """
        state_description = (
            f"Market conditions: RSI is {market_data.get('RSI', 'unknown')}. "
            f"Bollinger Band distance is {market_data.get('BB_dist', 'unknown')}. "
            f"MACD histogram is {market_data.get('MACD_hist', 'unknown')}."
        )
        
        logger.info(f"Input context: {state_description}")
        
        inputs = tokenizer(state_description, return_tensors="pt", truncation=True, max_length=128)
        
        with torch.no_grad():
            outputs = model(**inputs)
            logits = outputs.logits
            probabilities = torch.softmax(logits, dim=1)
            
            buy_prob = probabilities[0][1].item()
            decision = "Buy" if buy_prob > 0.5 else "No Buy"
            
            return {
                "decision": decision,
                "buy_probability": round(buy_prob, 4),
                "raw_logits": [round(x, 4) for x in logits[0].tolist()]
            }

    # Simulate market contexts
    scenarios = [
        {"RSI": 30.5, "BB_dist": -2.1, "MACD_hist": 0.05}, # Oversold
        {"RSI": 75.2, "BB_dist": 1.8, "MACD_hist": -0.1},  # Overbought
        {"RSI": 50.0, "BB_dist": 0.0, "MACD_hist": 0.0}    # Neutral
    ]
    
    for i, data in enumerate(scenarios):
        logger.info(f"--- Scenario {i+1} ---")
        result = decide_trade(data)
        logger.info(f"Decision Output: {json.dumps(result, indent=2)}\n")

if __name__ == "__main__":
    run_poc()
