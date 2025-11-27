FROM public.ecr.aws/lambda/python:3.9

# Copy requirements
COPY requirements.txt .

# Install dependencies
RUN pip install --upgrade pip && \
    pip install --prefer-binary --no-cache-dir \
    flask \
    apig_wsgi \
    "pandas<2.0.0" \
    "numpy<1.25.0" \
    "scikit-learn==1.3.0" \
    matplotlib \
    yfinance

# Copy application code and model
COPY app.py .
COPY model.pkl .

# Fix permissions (optional but good practice)
RUN chmod 644 app.py model.pkl requirements.txt

# Set the CMD to your handler (could also be done as a parameter override outside of the Dockerfile)
CMD [ "app.handler" ]
