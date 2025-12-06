import React, { useEffect, useState } from 'react';
import { Container, Typography, Box, Card, CardContent, CircularProgress, Alert } from '@mui/material';

interface DriftMetrics {
    tp: number;
    fp: number;
    tn: number;
    fn: number;
    total_predictions: number;
    accuracy: number;
    precision: number;
    recall: number;
    f1: number;
    dates: string[];
    actual_returns: number[];
    predicted_signals: number[];
}

const Reports: React.FC = () => {
    const [metrics, setMetrics] = useState<DriftMetrics | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        const fetchMetrics = async () => {
            try {
                const TRADING_API = process.env.REACT_APP_TRADING_API;
                if (!TRADING_API) {
                    throw new Error('Trading API not configured');
                }

                const response = await fetch(`${TRADING_API}/api/reports/daily-matrix`);
                if (!response.ok) {
                    throw new Error('Failed to fetch drift metrics');
                }

                const data = await response.json();
                setMetrics(data);
            } catch (err) {
                setError(err instanceof Error ? err.message : 'An error occurred');
            } finally {
                setLoading(false);
            }
        };

        fetchMetrics();
    }, []);

    if (loading) return <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}><CircularProgress /></Box>;
    if (error) return <Container sx={{ mt: 4 }}><Alert severity="error">{error}</Alert></Container>;

    return (
        <Container maxWidth="lg" sx={{ py: 4 }}>
            <Typography variant="h4" sx={{ mb: 4, fontWeight: 600 }}>Model Performance Report (Last 30 Days)</Typography>

            {/* Metrics Cards */}
            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr', md: '1fr 1fr 1fr 1fr' }, gap: 3, mb: 4 }}>
                <Card sx={{ height: '100%', bgcolor: '#e3f2fd' }}>
                    <CardContent>
                        <Typography color="textSecondary" gutterBottom>Total Predictions</Typography>
                        <Typography variant="h4">{metrics?.total_predictions}</Typography>
                    </CardContent>
                </Card>
                <Card sx={{ height: '100%', bgcolor: '#e8f5e9' }}>
                    <CardContent>
                        <Typography color="textSecondary" gutterBottom>Accuracy</Typography>
                        <Typography variant="h4">{(metrics?.accuracy || 0).toFixed(2)}</Typography>
                    </CardContent>
                </Card>
                <Card sx={{ height: '100%', bgcolor: '#fff3e0' }}>
                    <CardContent>
                        <Typography color="textSecondary" gutterBottom>Precision</Typography>
                        <Typography variant="h4">{(metrics?.precision || 0).toFixed(2)}</Typography>
                    </CardContent>
                </Card>
                <Card sx={{ height: '100%', bgcolor: '#f3e5f5' }}>
                    <CardContent>
                        <Typography color="textSecondary" gutterBottom>Recall</Typography>
                        <Typography variant="h4">{(metrics?.recall || 0).toFixed(2)}</Typography>
                    </CardContent>
                </Card>
            </Box>

            {/* Confusion Matrix */}
            <Card sx={{ mb: 4 }}>
                <CardContent>
                    <Typography variant="h6" sx={{ mb: 3 }}>Confusion Matrix (Model Signal vs Actual 5d Return)</Typography>
                    <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, maxWidth: 600, mx: 'auto' }}>
                        <Box sx={{ p: 3, bgcolor: '#c8e6c9', textAlign: 'center', borderRadius: 2 }}>
                            <Typography variant="h6">True Positive</Typography>
                            <Typography variant="h3">{metrics?.tp}</Typography>
                            <Typography variant="body2">Predicted Buy & Up</Typography>
                        </Box>
                        <Box sx={{ p: 3, bgcolor: '#ffcdd2', textAlign: 'center', borderRadius: 2 }}>
                            <Typography variant="h6">False Positive</Typography>
                            <Typography variant="h3">{metrics?.fp}</Typography>
                            <Typography variant="body2">Predicted Buy & Down</Typography>
                        </Box>
                        <Box sx={{ p: 3, bgcolor: '#ffcc80', textAlign: 'center', borderRadius: 2 }}>
                            <Typography variant="h6">False Negative</Typography>
                            <Typography variant="h3">{metrics?.fn}</Typography>
                            <Typography variant="body2">Predicted Sell & Up</Typography>
                        </Box>
                        <Box sx={{ p: 3, bgcolor: '#b3e5fc', textAlign: 'center', borderRadius: 2 }}>
                            <Typography variant="h6">True Negative</Typography>
                            <Typography variant="h3">{metrics?.tn}</Typography>
                            <Typography variant="body2">Predicted Sell & Down</Typography>
                        </Box>
                    </Box>
                </CardContent>
            </Card>

            {/* Drift Warning */}
            {(metrics?.accuracy || 1) < 0.5 && (
                <Alert severity="warning" sx={{ mt: 2 }}>
                    Model accuracy is below 50%. Potential model drift detected. Retraining recommended.
                </Alert>
            )}
        </Container>
    );
};

export default Reports;
