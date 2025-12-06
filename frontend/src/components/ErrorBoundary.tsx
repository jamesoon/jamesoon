import React, { Component, ErrorInfo, ReactNode } from 'react';
import { Box, Typography, Paper, Button } from '@mui/material';

interface Props {
    children: ReactNode;
}

interface State {
    hasError: boolean;
    error: Error | null;
    errorInfo: ErrorInfo | null;
}

class ErrorBoundary extends Component<Props, State> {
    public state: State = {
        hasError: false,
        error: null,
        errorInfo: null,
    };

    public static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error, errorInfo: null };
    }

    public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error('Uncaught error:', error, errorInfo);
        this.setState({ errorInfo });
    }

    public render() {
        if (this.state.hasError) {
            return (
                <Box
                    sx={{
                        display: 'flex',
                        justifyContent: 'center',
                        alignItems: 'center',
                        minHeight: '100vh',
                        p: 4,
                        bgcolor: '#f5f5f5',
                    }}
                >
                    <Paper sx={{ p: 4, maxWidth: 800, width: '100%', overflow: 'auto' }}>
                        <Typography variant="h4" color="error" gutterBottom>
                            Something went wrong
                        </Typography>
                        <Typography variant="body1" gutterBottom>
                            The application crashed. Here is the error details:
                        </Typography>

                        {this.state.error && (
                            <Box sx={{ mt: 2, mb: 2, p: 2, bgcolor: '#ffebee', borderRadius: 1 }}>
                                <Typography variant="subtitle1" fontWeight="bold" color="error">
                                    {this.state.error.toString()}
                                </Typography>
                            </Box>
                        )}

                        {this.state.errorInfo && (
                            <Box sx={{ mt: 2, p: 2, bgcolor: '#f8f9fa', borderRadius: 1, maxHeight: 400, overflow: 'auto' }}>
                                <Typography variant="caption" component="pre" sx={{ fontFamily: 'monospace' }}>
                                    {this.state.errorInfo.componentStack}
                                </Typography>
                            </Box>
                        )}

                        <Button
                            variant="contained"
                            color="primary"
                            onClick={() => window.location.reload()}
                            sx={{ mt: 3 }}
                        >
                            Reload Page
                        </Button>
                    </Paper>
                </Box>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
