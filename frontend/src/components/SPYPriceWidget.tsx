import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  CircularProgress,
  Chip,
  Divider,
  Alert,
  IconButton,
  Collapse,
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  AccessTime,
  ExpandMore,
  ExpandLess,
} from '@mui/icons-material';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
} from 'recharts';

interface SPYData {
  currentPrice: number;
  change: number;
  changePercent: number;
  previousClose: number;
  open: number;
  dayHigh: number;
  dayLow: number;
  volume: number;
  avgVolume: number;
  fiftyTwoWeekHigh: number;
  fiftyTwoWeekLow: number;
  lastUpdated: string;
  chartData: Array<{ date: string; price: number; }>;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: any[];
  label?: string;
}

const CustomTooltip: React.FC<CustomTooltipProps> = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <Paper sx={{ p: 1.5, bgcolor: 'rgba(255, 255, 255, 0.98)', boxShadow: 3 }}>
        <Typography variant="caption" sx={{ fontWeight: 600, display: 'block', mb: 0.5 }}>
          {label}
        </Typography>
        <Typography variant="body2" sx={{ color: '#667eea', fontWeight: 600 }}>
          ${payload[0].value.toFixed(2)}
        </Typography>
      </Paper>
    );
  }
  return null;
};

const SPYPriceWidget: React.FC = () => {
  const [spyData, setSPYData] = useState<SPYData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [timeRange, setTimeRange] = useState<'1D' | '5D' | '1M' | '3M'>('1M');
  const [expanded, setExpanded] = useState<boolean>(false);

  useEffect(() => {
    fetchSPYData();
    // Refresh data every 5 minutes
    const interval = setInterval(fetchSPYData, 300000);
    return () => clearInterval(interval);
  }, []);

  const fetchSPYData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Get API URL from environment variable
      const SPY_DATA_URL = process.env.REACT_APP_SPY_DATA_API || 'https://0qoytg0cfg.execute-api.ap-southeast-1.amazonaws.com/prod/api/spy-data';

      try {
        console.log('Fetching SPY data from:', SPY_DATA_URL);
        const response = await fetch(SPY_DATA_URL);

        if (response.ok) {
          const data = await response.json();
          setSPYData(data);
          console.log('✓ SPY data loaded from API:', data.dataSource);
          return;
        } else {
          console.warn('API returned error:', response.status, response.statusText);
        }
      } catch (apiError) {
        console.warn('API fetch failed, falling back to mock data:', apiError);
      }

      // Fallback to mock data if API is not available
      console.log('Using mock data (API not configured or unavailable)');
      const mockData = await generateMockSPYData();
      setSPYData(mockData);
    } catch (err: any) {
      setError('Failed to fetch SPY data');
      console.error('Error fetching SPY data:', err);
    } finally {
      setLoading(false);
    }
  };

  const generateMockSPYData = async (): Promise<SPYData> => {
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 500));

    const currentPrice = 659.03 + (Math.random() - 0.5) * 10;
    const previousClose = 652.53;
    const change = currentPrice - previousClose;
    const changePercent = (change / previousClose) * 100;

    // Generate 3-month historical data
    const chartData: Array<{ date: string; price: number; }> = [];
    const today = new Date();
    const threeMonthsAgo = new Date();
    threeMonthsAgo.setMonth(today.getMonth() - 3);

    let basePrice = 620;
    for (let d = new Date(threeMonthsAgo); d <= today; d.setDate(d.getDate() + 1)) {
      // Skip weekends
      if (d.getDay() !== 0 && d.getDay() !== 6) {
        basePrice += (Math.random() - 0.48) * 5; // Slight upward trend
        chartData.push({
          date: d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
          price: parseFloat(basePrice.toFixed(2)),
        });
      }
    }

    return {
      currentPrice,
      change,
      changePercent,
      previousClose,
      open: currentPrice - (Math.random() * 5),
      dayHigh: currentPrice + (Math.random() * 3),
      dayLow: currentPrice - (Math.random() * 3),
      volume: 115617357,
      avgVolume: 79021570,
      fiftyTwoWeekHigh: 689.70,
      fiftyTwoWeekLow: 481.80,
      lastUpdated: new Date().toLocaleString('en-US', {
        month: 'long',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true,
      }),
      chartData,
    };
  };

  if (loading && !spyData) {
    return (
      <Paper sx={{ p: 4, borderRadius: 3, textAlign: 'center' }}>
        <CircularProgress />
        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          Loading SPY data...
        </Typography>
      </Paper>
    );
  }

  if (error && !spyData) {
    return (
      <Paper sx={{ p: 3, borderRadius: 3 }}>
        <Alert severity="warning">{error}</Alert>
      </Paper>
    );
  }

  if (!spyData) return null;

  const isPositive = spyData.change >= 0;

  return (
    <Paper sx={{ p: 3, borderRadius: 3, border: '1px solid rgba(0,0,0,0.08)' }}>
      {/* Compact Header - Always Visible */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Box sx={{ flex: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 0.5 }}>
            <Typography variant="h6" sx={{ fontWeight: 700 }}>
              SPY
            </Typography>
            <Typography variant="h5" sx={{ fontWeight: 700 }}>
              {spyData.currentPrice.toFixed(2)}
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <Typography
                variant="body1"
                sx={{
                  color: isPositive ? '#4caf50' : '#f44336',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                {isPositive ? (
                  <TrendingUp sx={{ fontSize: 18 }} />
                ) : (
                  <TrendingDown sx={{ fontSize: 18 }} />
                )}
                {isPositive ? '+' : ''}{spyData.change.toFixed(2)}
              </Typography>
              <Typography
                variant="body1"
                sx={{
                  color: isPositive ? '#4caf50' : '#f44336',
                  fontWeight: 600,
                }}
              >
                ({isPositive ? '+' : ''}{spyData.changePercent.toFixed(2)}%)
              </Typography>
            </Box>
            <Chip
              label={`Prev: $${spyData.previousClose.toFixed(2)}`}
              size="small"
              sx={{ bgcolor: 'rgba(102, 126, 234, 0.1)', fontWeight: 600 }}
            />
          </Box>
          <Typography variant="caption" color="text.secondary">
            S&P 500 ETF • Updated: {spyData.lastUpdated}
          </Typography>
        </Box>

        {/* Expand/Collapse Button */}
        <IconButton
          onClick={() => setExpanded(!expanded)}
          sx={{
            bgcolor: 'rgba(102, 126, 234, 0.1)',
            '&:hover': {
              bgcolor: 'rgba(102, 126, 234, 0.2)',
            },
          }}
        >
          {expanded ? <ExpandLess /> : <ExpandMore />}
        </IconButton>
      </Box>

      {/* Expanded Content */}
      <Collapse in={expanded} timeout="auto" unmountOnExit>
        <Box sx={{ mt: 3 }}>

          {/* Time Range Selector */}
          <Box sx={{ mb: 2, display: 'flex', gap: 1 }}>
            {(['1D', '5D', '1M', '3M'] as const).map((range) => (
              <Chip
                key={range}
                label={range}
                size="small"
                onClick={() => setTimeRange(range)}
                sx={{
                  bgcolor: timeRange === range ? '#667eea' : 'transparent',
                  color: timeRange === range ? 'white' : 'text.secondary',
                  fontWeight: timeRange === range ? 600 : 400,
                  cursor: 'pointer',
                  '&:hover': {
                    bgcolor: timeRange === range ? '#667eea' : 'rgba(102, 126, 234, 0.1)',
                  },
                }}
              />
            ))}
          </Box>

          {/* Chart */}
          <Box sx={{ height: 200, mb: 3 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={spyData.chartData}>
                <defs>
                  <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#667eea" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#667eea" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11 }}
                  stroke="#999"
                  tickLine={false}
                  axisLine={false}
                  interval="preserveStartEnd"
                />
                <YAxis
                  domain={['dataMin - 5', 'dataMax + 5']}
                  tick={{ fontSize: 11 }}
                  stroke="#999"
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(value) => `$${value}`}
                />
                <Tooltip content={<CustomTooltip />} />
                <Area
                  type="monotone"
                  dataKey="price"
                  stroke="#667eea"
                  strokeWidth={2}
                  fill="url(#colorPrice)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </Box>

          <Divider sx={{ my: 2 }} />

          {/* Key Metrics */}
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Previous close
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                {spyData.previousClose.toFixed(2)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                52-week range
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                {spyData.fiftyTwoWeekLow.toFixed(2)} - {spyData.fiftyTwoWeekHigh.toFixed(2)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Open
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                {spyData.open.toFixed(2)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Volume
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                {spyData.volume.toLocaleString()}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Day's range
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                {spyData.dayLow.toFixed(2)} - {spyData.dayHigh.toFixed(2)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Avg. Volume
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                {spyData.avgVolume.toLocaleString()}
              </Typography>
            </Box>
          </Box>

          {/* Disclaimer */}
          <Box sx={{ mt: 3, p: 1.5, bgcolor: 'rgba(102, 126, 234, 0.05)', borderRadius: 1 }}>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
              ℹ️ Chart does not reflect overnight price. Data is for demonstration purposes.
            </Typography>
          </Box>
        </Box>
      </Collapse>
    </Paper>
  );
};

export default SPYPriceWidget;

