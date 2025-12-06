import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Box } from '@mui/material';
import { AppProvider, useApp } from './contexts/AppContext';
import ErrorBoundary from './components/ErrorBoundary';
import Login from './components/Login';
import Navigation from './components/Navigation';
import Portfolio from './components/Portfolio';
import Trading from './components/Trading';
import Prediction from './components/Prediction';
import Analytics from './components/Analytics';
import Reports from './components/Reports';
import Footer from './components/Footer';

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useApp();
  return isAuthenticated ? <>{children}</> : <Navigate to="/" />;
};

const AppContent: React.FC = () => {
  const { isAuthenticated } = useApp();

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      {isAuthenticated && <Navigation />}
      <Box sx={{ flex: 1 }}>
        <Routes>
          <Route path="/" element={<Login />} />
          <Route
            path="/portfolio"
            element={
              <ProtectedRoute>
                <Portfolio />
              </ProtectedRoute>
            }
          />
          <Route
            path="/trading"
            element={
              <ProtectedRoute>
                <Trading />
              </ProtectedRoute>
            }
          />
          <Route
            path="/prediction"
            element={
              <ProtectedRoute>
                <Prediction />
              </ProtectedRoute>
            }
          />
          <Route
            path="/analytics"
            element={
              <ProtectedRoute>
                <Analytics />
              </ProtectedRoute>
            }
          />
          <Route
            path="/reports"
            element={
              <ProtectedRoute>
                <Reports />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </Box>
      <Footer />
    </Box>
  );
};

const App: React.FC = () => {
  return (
    <AppProvider>
      <Router>
        <ErrorBoundary>
          <AppContent />
        </ErrorBoundary>
      </Router>
    </AppProvider>
  );
};

export default App;
