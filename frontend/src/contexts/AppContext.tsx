import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface Stock {
  ticker: string;
  shares: number;
  averagePrice: number;
  currentPrice: number;
}

interface Transaction {
  id: string;
  ticker: string;
  type: 'BUY' | 'SELL';
  shares: number;
  price: number;
  total: number;
  date: string;
}

interface AppState {
  isAuthenticated: boolean;
  username: string;
  cashBalance: number;
  initialBalance: number;
  portfolio: Stock[];
  transactions: Transaction[];
  login: (username: string) => void;
  logout: () => void;
  buyStock: (ticker: string, shares: number, price: number) => Promise<boolean>;
  sellStock: (ticker: string, shares: number, price: number) => Promise<boolean>;
  updateStockPrice: (ticker: string, price: number) => void;
}

const AppContext = createContext<AppState | undefined>(undefined);

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within AppProvider');
  }
  return context;
};

interface AppProviderProps {
  children: ReactNode;
}

export const AppProvider: React.FC<AppProviderProps> = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [username, setUsername] = useState('');
  const [cashBalance, setCashBalance] = useState(100000);
  const initialBalance = 100000;
  const [portfolio, setPortfolio] = useState<Stock[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const TRADING_API = process.env.REACT_APP_TRADING_API || '';

  // Load user data from backend on login
  const loadUserData = async (username: string) => {
    if (!TRADING_API) {
      console.warn('Trading API not configured, using local state only');
      return;
    }

    try {
      setIsLoading(true);

      // Load profile
      const profileRes = await fetch(`${TRADING_API}/api/trading/profile?username=${encodeURIComponent(username)}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      });

      if (profileRes.ok) {
        const profileData = await profileRes.json();
        setCashBalance(profileData.cashBalance || 100000);
      }

      // Load portfolio
      const portfolioRes = await fetch(`${TRADING_API}/api/trading/portfolio?username=${encodeURIComponent(username)}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      });

      if (portfolioRes.ok) {
        const portfolioData = await portfolioRes.json();
        setPortfolio(Array.isArray(portfolioData.portfolio) ? portfolioData.portfolio : []);
      }

      // Load transactions
      const transactionsRes = await fetch(`${TRADING_API}/api/trading/transactions?username=${encodeURIComponent(username)}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      });

      if (transactionsRes.ok) {
        const transactionsData = await transactionsRes.json();
        setTransactions(Array.isArray(transactionsData.transactions) ? transactionsData.transactions : []);
      }

    } catch (error) {
      console.error('Error loading user data:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const login = (username: string) => {
    setUsername(username);
    setIsAuthenticated(true);
    loadUserData(username);
  };

  const logout = () => {
    setUsername('');
    setIsAuthenticated(false);
  };

  const buyStock = async (ticker: string, shares: number, price: number): Promise<boolean> => {
    const total = shares * price;

    if (total > cashBalance) {
      return false; // Insufficient funds
    }

    // If API is configured, persist to backend
    if (TRADING_API && username) {
      try {
        const response = await fetch(`${TRADING_API}/api/trading/buy`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, ticker, shares, price })
        });

        if (!response.ok) {
          console.error('Failed to buy stock on backend');
          return false;
        }

        const data = await response.json();
        if (data.success) {
          // Reload data from backend
          await loadUserData(username);
          return true;
        }
        return false;
      } catch (error) {
        console.error('Error buying stock:', error);
        // Fall through to local update if API fails
      }
    }

    // Local-only update (fallback or no API configured)
    // Update cash balance
    setCashBalance(prev => prev - total);

    // Update portfolio
    setPortfolio(prev => {
      const existing = prev.find(s => s.ticker === ticker);
      if (existing) {
        const totalShares = existing.shares + shares;
        const newAvgPrice = ((existing.averagePrice * existing.shares) + (price * shares)) / totalShares;
        return prev.map(s =>
          s.ticker === ticker
            ? { ...s, shares: totalShares, averagePrice: newAvgPrice, currentPrice: price }
            : s
        );
      } else {
        return [...prev, { ticker, shares, averagePrice: price, currentPrice: price }];
      }
    });

    // Add transaction
    const transaction: Transaction = {
      id: Date.now().toString(),
      ticker,
      type: 'BUY',
      shares,
      price,
      total,
      date: new Date().toISOString(),
    };
    setTransactions(prev => [transaction, ...prev]);

    return true;
  };

  const sellStock = async (ticker: string, shares: number, price: number): Promise<boolean> => {
    const stock = portfolio.find(s => s.ticker === ticker);

    if (!stock || stock.shares < shares) {
      return false; // Insufficient shares
    }

    const total = shares * price;

    // If API is configured, persist to backend
    if (TRADING_API && username) {
      try {
        const response = await fetch(`${TRADING_API}/api/trading/sell`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, ticker, shares, price })
        });

        if (!response.ok) {
          console.error('Failed to sell stock on backend');
          return false;
        }

        const data = await response.json();
        if (data.success) {
          // Reload data from backend
          await loadUserData(username);
          return true;
        }
        return false;
      } catch (error) {
        console.error('Error selling stock:', error);
        // Fall through to local update if API fails
      }
    }

    // Local-only update (fallback or no API configured)
    // Update cash balance
    setCashBalance(prev => prev + total);

    // Update portfolio
    setPortfolio(prev => {
      return prev
        .map(s =>
          s.ticker === ticker
            ? { ...s, shares: s.shares - shares, currentPrice: price }
            : s
        )
        .filter(s => s.shares > 0); // Remove stocks with 0 shares
    });

    // Add transaction
    const transaction: Transaction = {
      id: Date.now().toString(),
      ticker,
      type: 'SELL',
      shares,
      price,
      total,
      date: new Date().toISOString(),
    };
    setTransactions(prev => [transaction, ...prev]);

    return true;
  };

  const updateStockPrice = (ticker: string, price: number) => {
    setPortfolio(prev =>
      prev.map(s => (s.ticker === ticker ? { ...s, currentPrice: price } : s))
    );
  };

  const value: AppState = {
    isAuthenticated,
    username,
    cashBalance,
    initialBalance,
    portfolio,
    transactions,
    login,
    logout,
    buyStock,
    sellStock,
    updateStockPrice,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};

