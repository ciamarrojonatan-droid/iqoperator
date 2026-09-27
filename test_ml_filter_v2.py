import ml_filter
import pandas as pd
import time

def test_ml_filter():
    print("[TEST] Loading ML Filter...")
    mf = ml_filter.get_ml_filter(model_path="models/xgb_filter_v2.pkl", threshold=0.6)
    
    if not mf.is_loaded:
        print("[TEST] FAILED: Model not loaded!")
        return
        
    print(f"[TEST] Model loaded successfully! {len(mf.feature_cols)} features.")
    
    print("[TEST] Loading test data...")
    df = pd.read_csv("data/BTCUSDT_M1_60d.csv").tail(200)
    
    print("[TEST] Testing inference...")
    t0 = time.perf_counter()
    allowed, prob = mf.filter_signal(df, signal="call")
    t1 = time.perf_counter()
    
    print(f"[TEST] Inference complete in {(t1-t0)*1000:.2f}ms")
    print(f"[TEST] Allowed: {allowed}, Probability: {prob:.4f}")

if __name__ == "__main__":
    test_ml_filter()
