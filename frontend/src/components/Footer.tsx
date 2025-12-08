import React from 'react';
import { Box, Typography, Container } from '@mui/material';

const Footer: React.FC = () => {
  return (
    <Box
      component="footer"
      sx={{
        py: 2,
        px: 2,
        mt: 'auto',
        backgroundColor: 'rgba(255, 255, 255, 0.9)',
        backdropFilter: 'blur(10px)',
        borderTop: '1px solid rgba(102, 126, 234, 0.2)',
      }}
    >
      <Container maxWidth="lg">
        <Typography
          variant="caption"
          color="text.secondary"
          align="center"
          sx={{ display: 'block', mb: 0.3, fontSize: '0.7rem' }}
        >
          © 2025 SUTD MDAI-E PRML Project
        </Typography>
        <Typography
          variant="caption"
          color="text.secondary"
          align="center"
          sx={{ display: 'block', mb: 0.3, fontSize: '0.7rem' }}
        >
          Developed by <strong>James Oon</strong>, <strong>Tung</strong>, and <strong>Josiah Lau</strong>
        </Typography>
        <Typography
          variant="caption"
          color="text.secondary"
          align="center"
          sx={{ display: 'block', fontSize: '0.7rem' }}
        >
          Singapore University of Technology and Design
        </Typography>
        <Typography
          variant="caption"
          color="text.secondary"
          align="center"
          sx={{ display: 'block', mt: 0.5, fontSize: '0.65rem', opacity: 0.7 }}
        >
          v1.07
        </Typography>
      </Container>
    </Box>
  );
};

export default Footer;

