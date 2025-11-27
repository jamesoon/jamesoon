import os
import pickle
import json
import io
import numpy as np
import pandas as pd
from sagemaker_containers.beta.framework import content_types, encoders

def model_fn(model_dir):
    """
    Load the model from the model_dir.
    """
    print(f"Loading model from {model_dir}")
    model_path = os.path.join(model_dir, "model.pkl")
    with open(model_path, "rb") as f:
        model_data = pickle.load(f)
    print("Model loaded successfully")
    return model_data

def input_fn(request_body, request_content_type):
    """
    Deserialize the request body.
    Supports text/csv and application/json.
    """
    print(f"Received request with content type: {request_content_type}")
    
    if request_content_type == content_types.JSON:
        # Expecting JSON: {"features": [[...]]} or just [[...]]
        input_data = json.loads(request_body)
        if isinstance(input_data, dict) and "features" in input_data:
            return pd.DataFrame(input_data["features"])
        return pd.DataFrame(input_data)
    
    elif request_content_type == content_types.CSV:
        # Expecting CSV without header
        return pd.read_csv(io.StringIO(request_body), header=None)
    
    else:
        raise ValueError(f"Unsupported content type: {request_content_type}")

def predict_fn(input_data, model):
    """
    Make a prediction using the model.
    """
    print("Executing prediction")
    
    # Ensure input matches expected columns if possible
    # The model dict contains 'feature_columns'
    if 'feature_columns' in model:
        # If input is just values (no headers), we assume order matches
        if len(input_data.columns) == len(model['feature_columns']):
            input_data.columns = model['feature_columns']
    
    prob_up = model['logistic_model'].predict_proba(input_data)[:, 1]
    pred_ret = model['linear_model'].predict(input_data)
    
    threshold = model.get('threshold', 0.5)
    signals = ["BUY" if p >= threshold else "SELL" for p in prob_up]
    
    # Return a dataframe or dict to be serialized
    # For Model Monitor, it's often best to return the prediction + probability
    # But the output_fn usually handles serialization.
    
    result = pd.DataFrame({
        "signal": signals,
        "prob_up": prob_up,
        "pred_return": pred_ret
    })
    
    return result

def output_fn(prediction, response_content_type):
    """
    Serialize the prediction result.
    """
    print(f"Serializing output to {response_content_type}")
    
    if response_content_type == content_types.JSON:
        return prediction.to_json(orient='records'), response_content_type
    
    elif response_content_type == content_types.CSV:
        return prediction.to_csv(index=False, header=False), response_content_type
        
    else:
        raise ValueError(f"Unsupported response content type: {response_content_type}")

if __name__ == '__main__':
    # For local testing
    pass
