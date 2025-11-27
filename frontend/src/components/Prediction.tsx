import React, { useState } from 'react';
import {
  Container,
  TextField,
  Button,
  Typography,
  Box,
  CircularProgress,
  Alert,
  Paper,
  Card,
  CardContent,
  Chip,
  Stack,
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  Psychology,
  ShowChart,
  CalendarToday,
  RocketLaunch,
  CheckCircle,
} from '@mui/icons-material';
import SPYPriceWidget from './SPYPriceWidget';

const Prediction: React.FC = () => {
  const [stockTicker] = useState<string>('SPY'); // Fixed to SPY only
  const [selectedDate, setSelectedDate] = useState<string>(new Date().toISOString().split('T')[0]);
  const [prediction, setPrediction] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [healthStatus, setHealthStatus] = useState<{ status: string, data?: any } | null>(null);
  const [healthLoading, setHealthLoading] = useState<boolean>(false);

  const handleHealthCheck = async () => {
    setHealthLoading(true);
    setHealthStatus(null);

    const API_URL = process.env.REACT_APP_PREDICTION_API;

    if (!API_URL) {
      setHealthStatus({ status: 'error', data: 'Prediction API URL not configured' });
      setHealthLoading(false);
      return;
    }

    try {
      // Replace /predict with /health
      const healthcheckUrl = API_URL.replace('/predict', '/health');
      const response = await fetch(healthcheckUrl, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setHealthStatus({ status: 'success', data });
    } catch (e: any) {
      setHealthStatus({ status: 'error', data: e.message || 'Failed to connect to healthcheck endpoint' });
    } finally {
      setHealthLoading(false);
    }
  };

  const handlePredict = async () => {
    setLoading(true);
    setError(null);
    setPrediction(null);

    const API_URL = process.env.REACT_APP_PREDICTION_API;

    if (!API_URL) {
      setError('Prediction API URL not configured. Please set REACT_APP_PREDICTION_API environment variable.');
      setLoading(false);
      return;
    }

    try {
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          // Send empty body to trigger fallback/dummy prediction for now
          // ticker: stockTicker.toUpperCase(),
          // date: selectedDate,
          // features: [1.0] 
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      // Handle new response format: { signal: "BUY" | "SELL", ... }
      const resultText = data.signal === 'BUY'
        ? `${stockTicker} price will likely go UP`
        : `${stockTicker} price will likely go DOWN`;
      setPrediction(resultText);
    } catch (e: any) {
      setError(e.message || 'Failed to connect to API. Please check your configuration.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {/* SPY Price Widget - Full Width */}
      <Box sx={{ mb: 4 }}>
        <SPYPriceWidget />
      </Box>

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1.6fr 1fr' }, gap: 4 }}>
        {/* Main Prediction Form */}
        <Box>
          <Paper sx={{ p: 4, borderRadius: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
              <Psychology sx={{ fontSize: 40, color: '#667eea' }} />
              <Box>
                <Typography variant="h5" sx={{ fontWeight: 600, color: '#667eea' }}>
                  AI-Powered Stock Prediction
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Machine Learning Model Deployment with AWS EKS & API Gateway
                </Typography>
              </Box>
            </Box>

            <Box sx={{ mb: 3, p: 2, bgcolor: 'rgba(102, 126, 234, 0.05)', borderRadius: 2, borderLeft: '4px solid #667eea' }}>
              <Typography variant="body2" color="text.secondary">
                This prediction system uses a <strong>Logistic Regression</strong> model specifically trained for <strong>SPY (S&P 500 ETF)</strong>.
                Enter a target date to get AI-powered insights on potential SPY price direction.
              </Typography>
            </Box>

            <Stack spacing={3}>
              <Box>
                <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
                  Stock Ticker
                </Typography>
                <TextField
                  variant="outlined"
                  fullWidth
                  value="SPY"
                  disabled
                  InputProps={{
                    startAdornment: <ShowChart sx={{ mr: 1, color: '#667eea', fontSize: 20 }} />,
                  }}
                  helperText="This model is optimized for SPY predictions only"
                  sx={{
                    '& .MuiInputBase-root': {
                      bgcolor: 'rgba(0, 0, 0, 0.02)',
                    }
                  }}
                />
              </Box>

              <Box>
                <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
                  Target Date
                </Typography>
                <TextField
                  type="date"
                  variant="outlined"
                  fullWidth
                  value={selectedDate}
                  onChange={(e) => setSelectedDate(e.target.value)}
                  InputLabelProps={{
                    shrink: true,
                  }}
                  InputProps={{
                    startAdornment: <CalendarToday sx={{ mr: 1, color: '#667eea', fontSize: 20 }} />,
                  }}
                />
              </Box>

              <Button
                variant="contained"
                size="large"
                fullWidth
                onClick={handlePredict}
                disabled={loading}
                sx={{
                  py: 1.5,
                  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  fontSize: '0.95rem',
                  fontWeight: 600,
                  boxShadow: '0 4px 15px rgba(102, 126, 234, 0.4)',
                  '&:hover': {
                    transform: 'translateY(-2px)',
                    boxShadow: '0 6px 20px rgba(102, 126, 234, 0.6)',
                    background: 'linear-gradient(135deg, #764ba2 0%, #f093fb 100%)',
                  },
                }}
              >
                {loading ? (
                  <CircularProgress size={24} sx={{ color: 'white' }} />
                ) : (
                  <>
                    <RocketLaunch sx={{ mr: 1 }} /> Get Prediction
                  </>
                )}
              </Button>
            </Stack>

            {/* Results Section */}
            {prediction && (
              <Box>
                <Alert
                  severity="success"
                  sx={{
                    mt: 3,
                    borderRadius: 2,
                    background: prediction.includes('UP')
                      ? 'linear-gradient(135deg, rgba(76, 175, 80, 0.1) 0%, rgba(56, 142, 60, 0.1) 100%)'
                      : 'linear-gradient(135deg, rgba(244, 67, 54, 0.1) 0%, rgba(198, 40, 40, 0.1) 100%)',
                    border: `2px solid ${prediction.includes('UP') ? '#4caf50' : '#f44336'}`,
                  }}
                  icon={
                    prediction.includes('UP') ? (
                      <TrendingUp sx={{ fontSize: 32, color: '#4caf50' }} />
                    ) : (
                      <TrendingDown sx={{ fontSize: 32, color: '#f44336' }} />
                    )
                  }
                >
                  <Typography variant="h6" sx={{ fontWeight: 600, color: prediction.includes('UP') ? '#4caf50' : '#f44336' }}>
                    Prediction Result
                  </Typography>
                  <Typography variant="body1" sx={{ mt: 1 }}>
                    {prediction.includes('UP') ? '📈' : '📉'} {prediction}
                  </Typography>
                </Alert>
              </Box>
            )}

            {error && (
              <Alert severity="error" sx={{ mt: 3, borderRadius: 2 }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>Error</Typography>
                <Typography variant="body2" sx={{ mt: 0.5 }}>{error}</Typography>
              </Alert>
            )}
          </Paper>
        </Box>

        {/* Sidebar */}
        <Box>
          {/* Health Check Card */}
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <CheckCircle sx={{ color: '#4caf50' }} />
                  <Typography variant="h6" sx={{ fontWeight: 600 }}>
                    API Health
                  </Typography>
                </Box>
              </Box>
              <Button
                variant="outlined"
                fullWidth
                onClick={handleHealthCheck}
                disabled={healthLoading}
                sx={{
                  mb: 2,
                  borderColor: '#4caf50',
                  color: '#4caf50',
                  '&:hover': {
                    borderColor: '#4caf50',
                    background: 'rgba(76, 175, 80, 0.1)',
                  },
                }}
              >
                {healthLoading ? <CircularProgress size={20} /> : 'Check API Status'}
              </Button>
              {healthStatus && (
                <Box>
                  {healthStatus.status === 'success' ? (
                    <Alert severity="success" sx={{ borderRadius: 2 }}>
                      <Typography variant="caption" sx={{ display: 'block', mb: 0.5 }}>
                        <strong>Status:</strong> {healthStatus.data?.status || 'healthy'}
                      </Typography>
                      {healthStatus.data && (
                        <>
                          <Typography variant="caption" sx={{ display: 'block' }}>
                            <strong>Service:</strong> {healthStatus.data.service}
                          </Typography>
                          <Typography variant="caption" sx={{ display: 'block' }}>
                            <strong>Model:</strong> {healthStatus.data.model_loaded ? 'Loaded' : 'Not Loaded'}
                          </Typography>
                        </>
                      )}
                    </Alert>
                  ) : (
                    <Alert severity="error" sx={{ borderRadius: 2 }}>
                      <Typography variant="caption">{healthStatus.data || 'Health check failed'}</Typography>
                    </Alert>
                  )}
                </Box>
              )}
            </CardContent>
          </Card>

          {/* Model Info Card */}
          <Card sx={{ background: 'linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%)' }}>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
                Model Details
              </Typography>
              <Stack spacing={1.5}>
                <Box>
                  <Chip label="Logistic Regression" size="small" sx={{ mb: 1, bgcolor: '#667eea', color: 'white' }} />
                  <Typography variant="body2" color="text.secondary">
                    Binary classification model for price direction prediction
                  </Typography>
                </Box>
                <Box>
                  <Chip label="AWS EKS" size="small" sx={{ mb: 1, bgcolor: '#764ba2', color: 'white' }} />
                  <Typography variant="body2" color="text.secondary">
                    Deployed on Kubernetes cluster for scalability
                  </Typography>
                </Box>
                <Box>
                  <Chip label="API Gateway" size="small" sx={{ mb: 1, bgcolor: '#f093fb', color: 'white' }} />
                  <Typography variant="body2" color="text.secondary">
                    RESTful API endpoint with Lambda proxy integration
                  </Typography>
                </Box>
              </Stack>
            </CardContent>
          </Card>
        </Box>
      </Box>
    </Container>
  );
};

export default Prediction;

