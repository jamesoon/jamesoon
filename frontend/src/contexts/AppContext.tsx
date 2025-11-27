import React, { createContext, useContext, useState, ReactNode } from 'react';

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
  buyStock: (ticker: string, shares: number, price: number) => boolean;
  sellStock: (ticker: string, shares: number, price: number) => boolean;
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

  const login = (username: string) => {
    setUsername(username);
    setIsAuthenticated(true);
  };

  const logout = () => {
    setUsername('');
    setIsAuthenticated(false);
  };

  const buyStock = (ticker: string, shares: number, price: number): boolean => {
    const total = shares * price;
    
    if (total > cashBalance) {
      return false; // Insufficient funds
    }

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

  const sellStock = (ticker: string, shares: number, price: number): boolean => {
    const stock = portfolio.find(s => s.ticker === ticker);
    
    if (!stock || stock.shares < shares) {
      return false; // Insufficient shares
    }

    const total = shares * price;

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

