# 🎯 START HERE - ML Model AWS Deployment

## 📌 Quick Status

**Project**: SPY Trading Prediction Model  
**Region**: ap-southeast-1 (Singapore)  
**Account**: 544794037284  
**Status**: ✅ **READY TO DEPLOY**

All scripts, configurations, and documentation are prepared. You can deploy with ONE command.

---



---

## 📋 What Gets Deployed

### Infrastructure Created
1. **EKS Cluster** (`ml-model-cluster`)
   - 2× t3.medium nodes
   - Full IAM permissions for S3 access
   
2. **Model Deployment** (Kubernetes)
   - 2 replicas for high availability
   - Health checks & resource limits
   - LoadBalancer service
   
3. **Lambda Proxy** (`ml-model-proxy`)
   - Connects API Gateway to EKS
   - Handles request forwarding
   
4. **API Gateway Integration**
   - `/healthcheck` (GET)
   - `/predict` (POST)
   - CORS enabled
   
5. **Frontend Update**
   - Configured with correct API Gateway URL
   - Deployed to S3 + CloudFront

### Using Existing Resources
- ✅ ECR: `ml-model-repo`
- ✅ S3: `mdaie-prml-spy-bucket` (market data)
- ✅ Lambda: `market-data-fetcher` (daily updates)
- ✅ API Gateway: `0qoytg0cfg`

---

## 📚 Documentation Structure

| Document | Purpose | When to Read |
|----------|---------|--------------|
| **START_HERE.md** (this file) | Quick start guide | Read first |
| **READY_TO_DEPLOY.md** | Deployment overview | Before running scripts |
| **QUICK_START.md** | Command reference | During deployment |
| **DEPLOYMENT_CHECKLIST.md** | Step-by-step + troubleshooting | If issues occur |
| **DEPLOYMENT_SUMMARY.md** | Executive summary | For overview |
| **INFERENCE_REQUIREMENTS.md** | Model technical details | For understanding model |

---

## 🔍 Pre-Flight Checks

Before deploying, verify:

```bash
# 1. AWS credentials
aws sts get-caller-identity
# Should show Account: 544794037284

# 2. Docker running
docker ps
# Should not error

# 3. kubectl installed
kubectl version --client
# Should show version

# 4. Files exist
ls -la ml_source/app.py ml_source/model.pkl Dockerfile
# All should exist

# 5. S3 data exists
aws s3 ls s3://mdaie-prml-spy-bucket/market-data/
# Should show latest.parquet
```

All checks passing? **You're ready to deploy!**

---

## 💻 Deployment Methods

### Option 1: Sequential Execution (Recommended)
Run the numbered scripts in the `scripts/` directory in order:

1. `bash scripts/01-setup_aws.sh`
2. `bash scripts/02-create_model.sh`
3. `python scripts/03-initial_s3_data_load.py`
... and so on.

Refer to [README.md](../README.md) for the full list.

### Option 2: Step-by-Step Manual
```bash
# See READY_TO_DEPLOY.md for commands
# Good for learning or debugging
```
- ✅ Full control
- ✅ Understand each step
- ⏱️ ~40 minutes (with manual checks)

---

## 🎯 After Deployment

### Verify Everything Works

1. **Check EKS**
   ```bash
   kubectl get pods
   # Should show 2 pods running
   ```

2. **Test API**
   ```bash
   curl https://0qoytg0cfg.execute-api.ap-southeast-1.amazonaws.com/prod/healthcheck
   # Should return {"status":"healthy",...}
   
   curl -X POST https://0qoytg0cfg.execute-api.ap-southeast-1.amazonaws.com/prod/predict \
     -H "Content-Type: application/json" \
     -d '{"ticker":"SPY"}'
   # Should return prediction
   ```

3. **Check Frontend**
   ```bash
   bash scripts/13-setup_cloudfront.sh
   # Note the Distribution Domain in the output
   ```

### Monitor Logs
```bash
# EKS pods
kubectl logs -f -l app=ml-model

# Lambda
aws logs tail /aws/lambda/ml-model-proxy --follow --region ap-southeast-1
```

---

## 💰 Cost Awareness

**Monthly Cost**: ~$138
- EKS control plane: $73/month
- 2× t3.medium nodes: $60/month
- Other services: <$5/month

**Hourly Cost**: ~$0.20/hour

**Cost Optimization**:
- Use Spot Instances: ~50% savings
- Scale down to 1 node if low traffic
- Delete when not needed:
  ```bash
  eksctl delete cluster --name ml-model-cluster --region ap-southeast-1
  ```

---

## 🆘 Troubleshooting

| Issue | Solution |
|-------|----------|
| Docker build fails | Check `ml_source/` files exist |
| EKS cluster creation fails | Check IAM permissions, quotas |
| Pods not starting | See `DEPLOYMENT_CHECKLIST.md` |
| API returns 502 | Check Lambda → EKS connectivity |
| High latency (>5s) | Check S3 data loading in logs |

**Full troubleshooting guide**: `DEPLOYMENT_CHECKLIST.md`

---

## 🎬 Ready to Deploy?

1. ✅ Read this file (you're here!)
2. ✅ Run pre-flight checks above
3. ✅ Execute master deployment:
   ```bash
   bash scripts/MASTER_DEPLOY.sh
   ```
4. ☕ Get coffee (20 min for EKS)
5. ✅ Verify deployment (tests included)
6. 🎉 Use your deployed ML model!

---

## 📞 Quick Reference

- **API Gateway ID**: `0qoytg0cfg`
- **API URL**: `https://0qoytg0cfg.execute-api.ap-southeast-1.amazonaws.com/prod`
- **S3 Bucket**: `mdaie-prml-spy-bucket`
- **ECR Repo**: `544794037284.dkr.ecr.ap-southeast-1.amazonaws.com/ml-model-repo`
- **Region**: `ap-southeast-1`

---

## 🚀 LET'S DEPLOY!

```bash
cd "/Users/jamesoon/Library/Mobile Documents/com~apple~CloudDocs/Desktop/PROJECTS/SUTD/MSTR-DAIE/MLOPS/Project"
bash scripts/MASTER_DEPLOY.sh
```

Good luck! 🎯
