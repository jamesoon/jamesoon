import boto3
import sagemaker
from sagemaker.model_monitor import DataCaptureConfig, DefaultModelMonitor, DatasetFormat, CronExpressionGenerator
from sagemaker.s3 import S3Uploader
import argparse
import os
import time

def setup_drift_monitoring(endpoint_name, s3_bucket, role_arn=None):
    """
    Sets up data capture and a model monitor for the specified endpoint.
    """
    session = s3.Session()
    sm_session = sagemaker.Session()
    sm_client = boto3.client('sagemaker')
    
    if role_arn is None:
        try:
            role_arn = sagemaker.get_execution_role()
        except ValueError:
            print("Could not get execution role. Please provide --role-arn.")
            return

    print(f"Setting up monitoring for endpoint: {endpoint_name}")
    print(f"Using S3 bucket: {s3_bucket}")
    print(f"Role: {role_arn}")

    # 1. Enable Data Capture
    print("\nStep 1: Enabling Data Capture...")
    capture_path = f"s3://{s3_bucket}/model-monitor/data-capture"
    
    data_capture_config = DataCaptureConfig(
        enable_capture=True,
        sampling_percentage=100,
        destination_s3_uri=capture_path
    )
    
    # Update endpoint to enable capture
    # Note: This might trigger an update which takes time
    predictor = sagemaker.Predictor(endpoint_name=endpoint_name)
    predictor.update_data_capture_config(data_capture_config)
    
    print(f"✓ Data Capture enabled. Data will be saved to: {capture_path}")
    
    # 2. Create Default Model Monitor
    print("\nStep 2: Creating Model Monitor...")
    monitor = DefaultModelMonitor(
        role=role_arn,
        instance_count=1,
        instance_type='ml.m5.large',
        volume_size_in_gb=20,
        max_runtime_in_seconds=3600,
    )
    
    # 3. Suggest Baseline Creation
    print("\nStep 3: Baseline Creation")
    print("To detect drift, you need a baseline computed from your training data.")
    print("Please run the following code snippet with your training dataset:")
    
    print(f"""
    # Example code to suggest baseline:
    from sagemaker.model_monitor import DefaultModelMonitor, DatasetFormat
    
    monitor = DefaultModelMonitor(
        role='{role_arn}',
        instance_count=1,
        instance_type='ml.m5.large',
        volume_size_in_gb=20,
        max_runtime_in_seconds=3600,
    )
    
    # Upload your training data to S3
    training_data_uri = 's3://{s3_bucket}/training-data/train.csv' 
    # (Make sure to upload your training dataframe there, without headers if CSV)
    
    monitor.suggest_baseline(
        baseline_dataset=training_data_uri,
        dataset_format=DatasetFormat.csv(header=False),
        output_s3_uri='s3://{s3_bucket}/model-monitor/baseline-results',
        wait=True
    )
    """)
    
    # 4. Schedule Monitoring
    print("\nStep 4: Schedule Monitoring (After Baseline)")
    print("Once the baseline is ready, you can schedule hourly/daily checks:")
    
    print(f"""
    monitor.create_monitoring_schedule(
        endpoint_input=predictor.endpoint,
        output_s3_uri='s3://{s3_bucket}/model-monitor/reports',
        statistics=monitor.baseline_statistics(),
        constraints=monitor.suggested_constraints(),
        schedule_cron_expression=CronExpressionGenerator.daily(),
        enable_cloudwatch_metrics=True,
    )
    """)
    
    print("\n✓ Setup instructions complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Setup SageMaker Drift Monitoring')
    parser.add_argument('--endpoint-name', type=str, required=True, help='Name of the SageMaker endpoint')
    parser.add_argument('--s3-bucket', type=str, required=True, help='S3 bucket for monitoring artifacts')
    parser.add_argument('--role-arn', type=str, help='IAM Role ARN for SageMaker')
    
    args = parser.parse_args()
    
    setup_drift_monitoring(args.endpoint_name, args.s3_bucket, args.role_arn)
