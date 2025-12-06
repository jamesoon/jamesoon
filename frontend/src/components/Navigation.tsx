import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  AppBar,
  Toolbar,
  Typography,
  Button,
  Box,
  IconButton,
  Avatar,
  Chip,
} from '@mui/material';
import {
  TrendingUp,
  AccountBalance,
  ShowChart,
  Psychology,
  Logout,
  Assessment,
  Summarize,
} from '@mui/icons-material';
import { useApp } from '../contexts/AppContext';

const Navigation: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { username, logout, cashBalance } = useApp();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  const isActive = (path: string) => location.pathname === path;

  return (
    <AppBar
      position="sticky"
      sx={{
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%)',
        boxShadow: '0 4px 20px rgba(102, 126, 234, 0.3)',
      }}
    >
      <Toolbar>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mr: 4 }}>
          <TrendingUp sx={{ fontSize: 28 }} />
          <Typography variant="h6" sx={{ fontWeight: 600, letterSpacing: '-0.5px' }}>
            MDAIE PROJECT
          </Typography>
          <Typography variant="body2" color="text.secondary">
            AI Powered Prediction Platform
          </Typography>
        </Box>

        <Box sx={{ flexGrow: 1, display: 'flex', gap: 1 }}>
          <Button
            color="inherit"
            startIcon={<AccountBalance />}
            onClick={() => navigate('/portfolio')}
            sx={{
              fontWeight: isActive('/portfolio') ? 600 : 400,
              borderBottom: isActive('/portfolio') ? '2px solid white' : 'none',
              borderRadius: 0,
              px: 2,
            }}
          >
            Portfolio
          </Button>
          <Button
            color="inherit"
            startIcon={<ShowChart />}
            onClick={() => navigate('/trading')}
            sx={{
              fontWeight: isActive('/trading') ? 600 : 400,
              borderBottom: isActive('/trading') ? '2px solid white' : 'none',
              borderRadius: 0,
              px: 2,
            }}
          >
            Trading
          </Button>
          <Button
            color="inherit"
            startIcon={<Psychology />}
            onClick={() => navigate('/prediction')}
            sx={{
              fontWeight: isActive('/prediction') ? 600 : 400,
              borderBottom: isActive('/prediction') ? '2px solid white' : 'none',
              borderRadius: 0,
              px: 2,
            }}
          >
            AI Prediction
          </Button>
          <Button
            color="inherit"
            startIcon={<Assessment />}
            onClick={() => navigate('/analytics')}
            sx={{
              fontWeight: isActive('/analytics') ? 600 : 400,
              borderBottom: isActive('/analytics') ? '2px solid white' : 'none',
              borderRadius: 0,
              px: 2,
            }}
          >
            Analytics
          </Button>
          <Button
            color="inherit"
            startIcon={<Summarize />}
            onClick={() => navigate('/reports')}
            sx={{
              fontWeight: isActive('/reports') ? 600 : 400,
              borderBottom: isActive('/reports') ? '2px solid white' : 'none',
              borderRadius: 0,
              px: 2,
            }}
          >
            Reports
          </Button>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Chip
            label={`$${cashBalance.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
            sx={{
              bgcolor: 'rgba(255, 255, 255, 0.2)',
              color: 'white',
              fontWeight: 600,
              fontSize: '0.85rem',
            }}
          />
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Avatar sx={{ width: 32, height: 32, bgcolor: 'rgba(255, 255, 255, 0.2)' }}>
              {username.charAt(0).toUpperCase()}
            </Avatar>
            <Typography variant="body2" sx={{ fontWeight: 500 }}>
              {username}
            </Typography>
          </Box>
          <IconButton color="inherit" onClick={handleLogout} title="Logout">
            <Logout />
          </IconButton>
        </Box>
      </Toolbar>
    </AppBar>
  );
};

export default Navigation;

