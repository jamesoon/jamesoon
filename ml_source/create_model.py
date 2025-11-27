
import pickle
import yfinance as yf
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

def create_model_from_yahoo():
    """Attempts to download data from Yahoo Finance and train a model."""
    print("Attempting to download AAPL data from Yahoo Finance...")
    data = yf.download('AAPL', start='2020-01-01', end='2023-01-01')
    
    if data.empty:
        raise ValueError("No data downloaded from Yahoo Finance.")
        
    print("Successfully downloaded data.")
    data['Price_Change'] = data['Close'].diff()
    data['Target'] = (data['Price_Change'] > 0).astype(int)
    data.dropna(inplace=True)
    
    X = data[['Price_Change']].shift(1).dropna()
    y = data['Target'].loc[X.index]
    
    return train_test_split(X, y, test_size=0.2, random_state=42)

def create_dummy_data():
    """Creates a dummy dataset if the Yahoo Finance download fails."""
    print("Falling back to creating dummy data.")
    X = pd.DataFrame({'Price_Change': [-0.5, 0.2, -0.1, 0.8, -0.3, 0.6, -0.4, 0.1, 0.9, -0.2]})
    y = pd.Series([0, 1, 0, 1, 0, 1, 0, 1, 1, 0])
    return train_test_split(X, y, test_size=0.2, random_state=42)

# --- Main script ---
try:
    X_train, X_test, y_train, y_test = create_model_from_yahoo()
except Exception as e:
    print(f"Could not create model from Yahoo Finance data: {e}")
    X_train, X_test, y_train, y_test = create_dummy_data()

# Create and train the model
print("Training a Logistic Regression model...")
model = LogisticRegression()
model.fit(X_train, y_train)

# Save the model to a pickle file
print("Saving the model to ml_source/model.pkl...")
with open('ml_source/model.pkl', 'wb') as f:
    pickle.dump(model, f)

print("Model creation complete.")
