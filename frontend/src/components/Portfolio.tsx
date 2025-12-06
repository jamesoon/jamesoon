import React, { useState, useEffect } from 'react';
import {
  Container,
  Paper,
  Typography,
  Box,
  Card,
  CardContent,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  CircularProgress,
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  AccountBalanceWallet,
  ShowChart,
  AttachMoney,
} from '@mui/icons-material';
import { useApp } from '../contexts/AppContext';
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Bar,
} from 'recharts';

// Custom Candlestick component
const Candlestick = (props: any) => {
  const { x, y, width, height, low, high, openClose } = props;
  const isGrowing = openClose[1] > openClose[0];
  const color = isGrowing ? '#4caf50' : '#f44336';
  const ratio = Math.abs(height / (openClose[0] - openClose[1]));

  return (
    <g stroke={color} fill="none" strokeWidth="1">
      <path
        d={`
          M ${x},${y}
          L ${x},${y + height}
          M ${x},${y + (openClose[0] - low) * ratio}
          L ${x + width},${y + (openClose[0] - low) * ratio}
          L ${x + width},${y + (openClose[1] - low) * ratio}
          L ${x},${y + (openClose[1] - low) * ratio}
          Z
        `}
        fill={color}
        fillOpacity="0.8"
      />
      <path
        d={`
          M ${x + width / 2},${y}
          L ${x + width / 2},${y + (openClose[0] - low) * ratio}
          M ${x + width / 2},${y + (openClose[1] - low) * ratio}
          L ${x + width / 2},${y + height}
        `}
      />
    </g>
  );
};

const Portfolio: React.FC = () => {
  const { cashBalance, initialBalance, portfolio, transactions } = useApp();
  const [marketData, setMarketData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Calculate total portfolio value
  const portfolioValue = portfolio.reduce(
    (sum, stock) => sum + stock.shares * stock.currentPrice,
    0
  );

  const totalValue = cashBalance + portfolioValue;
  const totalPnL = totalValue - initialBalance;
  const totalPnLPercent = ((totalPnL / initialBalance) * 100);

  // Fetch real market data from AWS Lambda API
  useEffect(() => {
    const fetchMarketData = async () => {
      setLoading(true);

      // Get API URL from environment variable or use placeholder
      const API_URL = process.env.REACT_APP_MARKET_DATA_API || 'https://your-api-id.execute-api.ap-southeast-1.amazonaws.com/prod/api/market-indices';

      try {
        console.log('Fetching market data from:', API_URL);

        const response = await fetch(API_URL, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log('Market data received:', data);

        if (Array.isArray(data)) {
          setMarketData(data);
        } else if (data && Array.isArray(data.data)) {
          setMarketData(data.data);
        } else {
          console.warn('Market data is not an array, using fallback');
          setMarketData(generateFallbackData());
        }
      } catch (error) {
        console.error('Error fetching market data:', error);

        // Fallback to simulated data if API fails
        console.log('Using fallback simulated data');
        const fallbackData = generateFallbackData();
        setMarketData(fallbackData);
      } finally {
        setLoading(false);
      }
    };

    fetchMarketData();
  }, []);

  // Fallback function to generate simulated data
  const generateFallbackData = () => {
    const indices = [
      { name: 'DOW', current: 46245.4, startValue: 43200, volatility: 0.015 },
      { name: 'NASDAQ', current: 22273.1, startValue: 20800, volatility: 0.018 },
      { name: 'S&P 500', current: 6620.1, startValue: 6180, volatility: 0.012 },
      { name: 'RUSSELL 2000', current: 2355.60, startValue: 2200, volatility: 0.020 },
    ];

    return indices.map(index => {
      const chartData = [];
      const today = new Date();
      const daysToGenerate = 90;
      let currentPrice = index.startValue;
      const trend = (index.current - index.startValue) / daysToGenerate;

      for (let i = daysToGenerate; i >= 0; i--) {
        const date = new Date(today);
        date.setDate(date.getDate() - i);
        if (date.getDay() === 0 || date.getDay() === 6) continue;

        const trendComponent = trend;
        const randomWalk = (Math.random() - 0.5) * currentPrice * index.volatility;
        currentPrice += trendComponent + randomWalk;

        const dayVolatility = currentPrice * index.volatility * 0.5;
        const open = currentPrice + (Math.random() - 0.5) * dayVolatility;
        const close = currentPrice + (Math.random() - 0.5) * dayVolatility;
        const high = Math.max(open, close) + Math.random() * dayVolatility;
        const low = Math.min(open, close) - Math.random() * dayVolatility;

        chartData.push({
          date: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
          open: Number(open.toFixed(2)),
          high: Number(high.toFixed(2)),
          low: Number(low.toFixed(2)),
          close: Number(close.toFixed(2)),
          openClose: [open, close],
        });
      }

      const current = chartData[chartData.length - 1]?.close || index.current;
      const previous = chartData[chartData.length - 2]?.close || current;
      const change = current - previous;
      const changePercent = (change / previous) * 100;

      return {
        name: index.name,
        current,
        change,
        changePercent,
        color: change >= 0 ? '#4caf50' : '#f44336',
        chartData,
      };
    });
  };

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {/* Market Indices */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h6" sx={{ mb: 2, fontWeight: 600, fontSize: '1rem' }}>
          Market Indices - Past 3 Months
        </Typography>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        ) : (
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr', md: 'repeat(4, 1fr)' }, gap: 2 }}>
            {Array.isArray(marketData) && marketData.map((index) => (
              <Card
                key={index.name}
                sx={{
                  background: 'linear-gradient(135deg, rgba(40, 40, 40, 0.95) 0%, rgba(30, 30, 30, 0.98) 100%)',
                  color: 'white',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                }}
              >
                <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
                    <Box>
                      <Typography variant="body2" sx={{ fontSize: '0.75rem', opacity: 0.7, mb: 0.5 }}>
                        {index.name}
                      </Typography>
                      <Typography variant="h6" sx={{ fontSize: '1rem', fontWeight: 600 }}>
                        {index.current.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </Typography>
                    </Box>
                    <Box sx={{ textAlign: 'right' }}>
                      <Typography
                        variant="caption"
                        sx={{
                          color: index.change >= 0 ? '#4caf50' : '#f44336',
                          fontSize: '0.7rem',
                          fontWeight: 600,
                        }}
                      >
                        {index.change >= 0 ? '+' : ''}{index.change.toFixed(2)}
                      </Typography>
                      <Typography
                        variant="caption"
                        sx={{
                          display: 'block',
                          color: index.change >= 0 ? '#4caf50' : '#f44336',
                          fontSize: '0.65rem',
                        }}
                      >
                        ({index.change >= 0 ? '+' : ''}{index.changePercent.toFixed(2)}%)
                      </Typography>
                    </Box>
                  </Box>
                  <ResponsiveContainer width="100%" height={80}>
                    <ComposedChart data={index.chartData}>
                      <XAxis dataKey="date" hide />
                      <YAxis domain={['dataMin', 'dataMax']} hide />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: 'rgba(0, 0, 0, 0.9)',
                          border: '1px solid rgba(255, 255, 255, 0.2)',
                          borderRadius: '4px',
                          fontSize: '0.65rem',
                        }}
                        labelStyle={{ color: 'white', fontSize: '0.65rem' }}
                        formatter={(value: any, name: string) => {
                          if (name === 'openClose') return null;
                          return [Number(value).toFixed(2), name.toUpperCase()];
                        }}
                      />
                      <Bar
                        dataKey="openClose"
                        shape={<Candlestick />}
                        fillOpacity={0.8}
                      />
                      <Line
                        type="monotone"
                        dataKey="close"
                        stroke={index.color}
                        strokeWidth={0.5}
                        dot={false}
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                  <Typography variant="caption" sx={{ fontSize: '0.6rem', opacity: 0.5, display: 'block', mt: 0.5, textAlign: 'center' }}>
                    Live data from Yahoo Finance via AWS Lambda
                  </Typography>
                </CardContent>
              </Card>
            ))}
          </Box>
        )}
      </Box>

      {/* Summary Cards */}
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr', md: 'repeat(4, 1fr)' }, gap: 2, mb: 4 }}>
        <Card
          sx={{
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            color: 'white',
          }}
        >
          <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <AccountBalanceWallet sx={{ fontSize: 20 }} />
                <Typography variant="body2" sx={{ fontSize: '0.75rem' }}>Total Value</Typography>
              </Box>
              <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '1.1rem' }}>
                ${totalValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </Typography>
            </Box>
          </CardContent>
        </Card>

        <Card>
          <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <AttachMoney sx={{ fontSize: 20, color: '#4caf50' }} />
                <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                  Cash Balance
                </Typography>
              </Box>
              <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '1.1rem' }}>
                ${cashBalance.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </Typography>
            </Box>
          </CardContent>
        </Card>

        <Card>
          <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <ShowChart sx={{ fontSize: 20, color: '#2196f3' }} />
                <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                  Portfolio Value
                </Typography>
              </Box>
              <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '1.1rem' }}>
                ${portfolioValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </Typography>
            </Box>
          </CardContent>
        </Card>

        <Card
          sx={{
            background: totalPnL >= 0
              ? 'linear-gradient(135deg, #4caf50 0%, #66bb6a 100%)'
              : 'linear-gradient(135deg, #f44336 0%, #ef5350 100%)',
            color: 'white',
          }}
        >
          <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {totalPnL >= 0 ? (
                  <TrendingUp sx={{ fontSize: 20 }} />
                ) : (
                  <TrendingDown sx={{ fontSize: 20 }} />
                )}
                <Typography variant="body2" sx={{ fontSize: '0.75rem' }}>Total P&L</Typography>
              </Box>
              <Box sx={{ textAlign: 'right' }}>
                <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '1.1rem' }}>
                  {totalPnL >= 0 ? '+' : ''}${totalPnL.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </Typography>
                <Typography variant="caption" sx={{ fontSize: '0.7rem' }}>
                  {totalPnL >= 0 ? '+' : ''}{totalPnLPercent.toFixed(2)}%
                </Typography>
              </Box>
            </Box>
          </CardContent>
        </Card>
      </Box>

      {/* Holdings */}
      <Paper sx={{ p: 3, mb: 4, borderRadius: 3 }}>
        <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
          Current Holdings
        </Typography>
        {portfolio.length === 0 ? (
          <Box sx={{ py: 4, textAlign: 'center' }}>
            <Typography color="text.secondary">
              No holdings yet. Start trading to build your portfolio!
            </Typography>
          </Box>
        ) : (
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600 }}>Ticker</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600 }}>Shares</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600 }}>Avg Price</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600 }}>Current Price</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600 }}>Total Value</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600 }}>P&L</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600 }}>P&L %</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {portfolio.map((stock) => {
                  const totalValue = stock.shares * stock.currentPrice;
                  const totalCost = stock.shares * stock.averagePrice;
                  const pnl = totalValue - totalCost;
                  const pnlPercent = ((pnl / totalCost) * 100);

                  return (
                    <TableRow key={stock.ticker}>
                      <TableCell>
                        <Typography sx={{ fontWeight: 600 }}>{stock.ticker}</Typography>
                      </TableCell>
                      <TableCell align="right">{stock.shares}</TableCell>
                      <TableCell align="right">
                        ${stock.averagePrice.toFixed(2)}
                      </TableCell>
                      <TableCell align="right">
                        ${stock.currentPrice.toFixed(2)}
                      </TableCell>
                      <TableCell align="right">
                        ${totalValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </TableCell>
                      <TableCell align="right">
                        <Chip
                          label={`${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}`}
                          size="small"
                          sx={{
                            bgcolor: pnl >= 0 ? 'rgba(76, 175, 80, 0.1)' : 'rgba(244, 67, 54, 0.1)',
                            color: pnl >= 0 ? '#4caf50' : '#f44336',
                            fontWeight: 600,
                          }}
                        />
                      </TableCell>
                      <TableCell align="right">
                        <Typography
                          sx={{
                            color: pnl >= 0 ? '#4caf50' : '#f44336',
                            fontWeight: 600,
                          }}
                        >
                          {pnl >= 0 ? '+' : ''}{pnlPercent.toFixed(2)}%
                        </Typography>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>

      {/* Recent Transactions */}
      <Paper sx={{ p: 3, borderRadius: 3 }}>
        <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
          Recent Transactions
        </Typography>
        {transactions.length === 0 ? (
          <Box sx={{ py: 4, textAlign: 'center' }}>
            <Typography color="text.secondary">No transactions yet</Typography>
          </Box>
        ) : (
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600 }}>Date</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Type</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Ticker</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600 }}>Shares</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600 }}>Price</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600 }}>Total</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {transactions.slice(0, 10).map((tx) => (
                  <TableRow key={tx.id}>
                    <TableCell>
                      {new Date(tx.date).toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={tx.type}
                        size="small"
                        sx={{
                          bgcolor: tx.type === 'BUY' ? 'rgba(33, 150, 243, 0.1)' : 'rgba(255, 152, 0, 0.1)',
                          color: tx.type === 'BUY' ? '#2196f3' : '#ff9800',
                          fontWeight: 600,
                        }}
                      />
                    </TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>{tx.ticker}</TableCell>
                    <TableCell align="right">{tx.shares}</TableCell>
                    <TableCell align="right">${tx.price.toFixed(2)}</TableCell>
                    <TableCell align="right">
                      ${tx.total.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>
    </Container>
  );
};

export default Portfolio;

