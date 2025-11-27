# SUTD Stock Trading Platform - Frontend Structure

## 🎉 Application Overview

A complete stock trading platform with AI-powered predictions, built with React, TypeScript, and Material-UI.

## 📁 Project Structure

```
frontend/
├── src/
│   ├── contexts/
│   │   └── AppContext.tsx          # Global state management (auth, portfolio, trading)
│   ├── components/
│   │   ├── Login.tsx               # Authentication page (stub)
│   │   ├── Navigation.tsx          # Top navigation bar
│   │   ├── Portfolio.tsx           # Portfolio overview with P&L tracking
│   │   ├── Trading.tsx             # Buy/Sell trading interface
│   │   └── Prediction.tsx          # AI prediction (refactored)
│   ├── App.tsx                     # Main app with routing
│   ├── index.tsx                   # React entry point
│   └── index.css                   # Global styles
└── public/
    └── index.html                  # HTML template
```

## 🚀 Features Implemented

### 1. **Login Page** (`/`)
- Stub authentication (enter any username)
- Clean, professional UI with Material-UI
- Redirects to portfolio on successful login

### 2. **Portfolio Page** (`/portfolio`)
- **Initial Balance**: $100,000 USD
- **Summary Cards**: Total value, cash balance, portfolio value, total P&L
- **Holdings Table**: View all positions with real-time P&L calculations
- **Transaction History**: Complete audit trail of all trades

### 3. **Trading Page** (`/trading`)
- **Buy/Sell Toggle**: Switch between buy and sell modes
- **Real-time Validation**: Checks for sufficient funds/shares
- **Transaction Recording**: All trades are logged
- **Portfolio Updates**: Automatic balance and position updates
- **Success/Error Notifications**: User feedback for all actions

### 4. **AI Prediction Page** (`/prediction`)
- **Professional Redesign**: Cleaner, more focused interface
- **ML Model Integration**: Logistic Regression predictions
- **Health Check**: API status monitoring
- **Model Information**: Detailed deployment info
- **Retained Font Sizes**: Same typography as original

## 🎨 Design Highlights

- **Gradient Theme**: Purple/blue gradient background
- **Professional UI**: Material-UI components throughout
- **Responsive Layout**: Works on desktop and mobile
- **Smooth Navigation**: React Router with protected routes
- **Real-time Updates**: State management with Context API

## 💰 Portfolio Management

### State Management
- Initial funding: **$100,000**
- Cash balance tracking
- Stock positions with average cost basis
- Real-time P&L calculations
- Transaction history

### Trading Features
- **Buy Stocks**: Validates sufficient funds
- **Sell Stocks**: Validates sufficient shares
- **Price Tracking**: Updates current prices per trade
- **Average Cost**: Calculates weighted average cost basis
- **P&L Calculation**: Shows unrealized gains/losses

## 🔐 Authentication Flow

1. User enters username on login page
2. System authenticates (stub - no password validation)
3. Redirects to portfolio page
4. Protected routes require authentication
5. Logout returns to login page

## 🛠️ Technical Stack

- **React 18** with TypeScript
- **Material-UI v5** for components
- **React Router v6** for navigation
- **Context API** for state management
- **Recharts** for visualizations (if needed)

## 📝 Usage

### Starting the Application
```bash
cd frontend
npm start
```

### Default Login
- Username: Any value
- Password: Any value (not validated)

### Trading Workflow
1. Login → Redirects to Portfolio
2. Navigate to Trading page
3. Select BUY or SELL
4. Enter ticker, shares, and price
5. Execute trade
6. View updated portfolio

### Getting Predictions
1. Navigate to AI Prediction page
2. Enter stock ticker (e.g., AAPL)
3. Select target date
4. Click "Get Prediction"
5. View ML-powered forecast

## 🌐 API Configuration

Set the API Gateway URL in `.env`:
```bash
REACT_APP_API_URL=your_api_gateway_url
```

## 📊 Current State

- ✅ Multi-page application with routing
- ✅ Login page (stub authentication)
- ✅ Portfolio page with $100k initial funding
- ✅ Trading page with buy/sell functionality
- ✅ AI Prediction page (refactored)
- ✅ Real-time P&L tracking
- ✅ Transaction history
- ✅ Professional UI design
- ✅ Responsive navigation

## 🎯 Access the Application

**URL**: http://localhost:3000

**Default Pages**:
- `/` - Login
- `/portfolio` - Portfolio Overview
- `/trading` - Buy/Sell Trading
- `/prediction` - AI Predictions

---

**Developed for SUTD MDAI-E PRML Project**

