import React, { useState } from 'react';
import {
  Container,
  Paper,
  Typography,
  Box,
  TextField,
  Button,
  Card,
  CardContent,
  Alert,
  Snackbar,
  ToggleButton,
  ToggleButtonGroup,
  Divider,
  Chip,
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  AttachMoney,
  ShowChart,
} from '@mui/icons-material';
import { useApp } from '../contexts/AppContext';
import SPYPriceWidget from './SPYPriceWidget';

const Trading: React.FC = () => {
  const { buyStock, sellStock, cashBalance, portfolio } = useApp();
  const [ticker] = useState('SPY'); // Fixed to SPY only
  const [shares, setShares] = useState<number>(0);
  const [price, setPrice] = useState<number>(0);
  const [tradeType, setTradeType] = useState<'BUY' | 'SELL'>('BUY');
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: 'success' | 'error';
  }>({ open: false, message: '', severity: 'success' });

  const handleTrade = () => {
    if (!ticker || shares <= 0 || price <= 0) {
      setSnackbar({
        open: true,
        message: 'Please fill in all fields with valid values',
        severity: 'error',
      });
      return;
    }

    // Ensure only SPY can be traded
    if (ticker.toUpperCase() !== 'SPY') {
      setSnackbar({
        open: true,
        message: 'Only SPY (S&P 500 ETF) trading is supported',
        severity: 'error',
      });
      return;
    }

    let success = false;
    if (tradeType === 'BUY') {
      success = buyStock('SPY', shares, price);
      if (success) {
        setSnackbar({
          open: true,
          message: `Successfully bought ${shares} shares of ${ticker.toUpperCase()} at $${price.toFixed(2)}`,
          severity: 'success',
        });
        // Reset form
        setShares(0);
      } else {
        setSnackbar({
          open: true,
          message: 'Insufficient funds to complete this purchase',
          severity: 'error',
        });
      }
    } else {
      success = sellStock('SPY', shares, price);
      if (success) {
        setSnackbar({
          open: true,
          message: `Successfully sold ${shares} shares of ${ticker.toUpperCase()} at $${price.toFixed(2)}`,
          severity: 'success',
        });
        // Reset form
        setShares(0);
      } else {
        setSnackbar({
          open: true,
          message: 'Insufficient shares to complete this sale',
          severity: 'error',
        });
      }
    }
  };

  const totalCost = shares * price;
  const currentStock = portfolio.find(s => s.ticker === 'SPY');

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {/* SPY Price Widget - Full Width */}
      <Box sx={{ mb: 4 }}>
        <SPYPriceWidget />
      </Box>

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1.4fr 1fr' }, gap: 4 }}>
        {/* Trading Form */}
        <Box>
          <Paper sx={{ p: 4, borderRadius: 3 }}>
            <Typography variant="h5" sx={{ mb: 3, fontWeight: 600 }}>
              Execute Trade
            </Typography>

            <Box sx={{ mb: 3 }}>
              <ToggleButtonGroup
                value={tradeType}
                exclusive
                onChange={(_, value) => value && setTradeType(value)}
                fullWidth
                sx={{ mb: 3 }}
              >
                <ToggleButton
                  value="BUY"
                  sx={{
                    py: 1.5,
                    '&.Mui-selected': {
                      bgcolor: 'rgba(33, 150, 243, 0.2)',
                      color: '#2196f3',
                      fontWeight: 600,
                      '&:hover': {
                        bgcolor: 'rgba(33, 150, 243, 0.3)',
                      },
                    },
                  }}
                >
                  <TrendingUp sx={{ mr: 1 }} />
                  Buy
                </ToggleButton>
                <ToggleButton
                  value="SELL"
                  sx={{
                    py: 1.5,
                    '&.Mui-selected': {
                      bgcolor: 'rgba(255, 152, 0, 0.2)',
                      color: '#ff9800',
                      fontWeight: 600,
                      '&:hover': {
                        bgcolor: 'rgba(255, 152, 0, 0.3)',
                      },
                    },
                  }}
                >
                  <TrendingDown sx={{ mr: 1 }} />
                  Sell
                </ToggleButton>
              </ToggleButtonGroup>

              <TextField
                label="Stock Ticker"
                variant="outlined"
                fullWidth
                value="SPY"
                disabled
                helperText="Trading is limited to SPY (S&P 500 ETF) only"
                sx={{ 
                  mb: 2,
                  '& .MuiInputBase-root': {
                    bgcolor: 'rgba(0, 0, 0, 0.02)',
                  }
                }}
                InputProps={{
                  startAdornment: <ShowChart sx={{ mr: 1, color: '#667eea' }} />,
                }}
              />

              <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, mb: 2 }}>
                <TextField
                  label="Shares"
                  type="number"
                  variant="outlined"
                  fullWidth
                  value={shares || ''}
                  onChange={(e) => setShares(Number(e.target.value))}
                  inputProps={{ min: 0, step: 1 }}
                />
                <TextField
                  label="Price per Share"
                  type="number"
                  variant="outlined"
                  fullWidth
                  value={price || ''}
                  onChange={(e) => setPrice(Number(e.target.value))}
                  inputProps={{ min: 0, step: 0.01 }}
                  InputProps={{
                    startAdornment: <AttachMoney sx={{ fontSize: 18 }} />,
                  }}
                />
              </Box>

              <Divider sx={{ my: 3 }} />

              <Box sx={{ mb: 3 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                  <Typography color="text.secondary">Total {tradeType === 'BUY' ? 'Cost' : 'Proceeds'}:</Typography>
                  <Typography sx={{ fontWeight: 600, fontSize: '1.1rem' }}>
                    ${totalCost.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography color="text.secondary">Available Cash:</Typography>
                  <Typography sx={{ fontWeight: 600 }}>
                    ${cashBalance.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </Typography>
                </Box>
                {tradeType === 'SELL' && currentStock && (
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1 }}>
                    <Typography color="text.secondary">Shares Owned:</Typography>
                    <Typography sx={{ fontWeight: 600 }}>{currentStock.shares}</Typography>
                  </Box>
                )}
              </Box>

              <Button
                variant="contained"
                fullWidth
                size="large"
                onClick={handleTrade}
                sx={{
                  py: 1.5,
                  background: tradeType === 'BUY'
                    ? 'linear-gradient(135deg, #2196f3 0%, #1976d2 100%)'
                    : 'linear-gradient(135deg, #ff9800 0%, #f57c00 100%)',
                  fontSize: '0.95rem',
                  fontWeight: 600,
                  boxShadow: '0 4px 15px rgba(0, 0, 0, 0.2)',
                  '&:hover': {
                    transform: 'translateY(-2px)',
                    boxShadow: '0 6px 20px rgba(0, 0, 0, 0.3)',
                  },
                }}
              >
                {tradeType === 'BUY' ? 'Buy' : 'Sell'} SPY
              </Button>
            </Box>
          </Paper>
        </Box>

        {/* Market Info & Tips */}
        <Box>
          <Card sx={{ mb: 3, background: 'linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%)' }}>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
                Trading Information
              </Typography>
              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary" paragraph>
                  <strong>Current Balance:</strong> ${cashBalance.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </Typography>
                <Typography variant="body2" color="text.secondary" paragraph>
                  <strong>Portfolio Value:</strong> ${portfolio.reduce((sum, s) => sum + s.shares * s.currentPrice, 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </Typography>
              </Box>
            </CardContent>
          </Card>

          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
                Quick Tips
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <Box>
                  <Chip
                    label="Tip 1"
                    size="small"
                    sx={{ mb: 1, bgcolor: '#667eea', color: 'white' }}
                  />
                  <Typography variant="body2" color="text.secondary">
                    Use the AI Prediction page to get ML-powered insights before trading
                  </Typography>
                </Box>
                <Box>
                  <Chip
                    label="Tip 2"
                    size="small"
                    sx={{ mb: 1, bgcolor: '#764ba2', color: 'white' }}
                  />
                  <Typography variant="body2" color="text.secondary">
                    Monitor your portfolio regularly to track profits and losses
                  </Typography>
                </Box>
                <Box>
                  <Chip
                    label="SPY Only"
                    size="small"
                    sx={{ mb: 1, bgcolor: '#f093fb', color: 'white' }}
                  />
                  <Typography variant="body2" color="text.secondary">
                    This platform focuses on SPY (S&P 500 ETF) trading, providing broad market exposure
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Box>
      </Box>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          severity={snackbar.severity}
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Container>
  );
};

export default Trading;

