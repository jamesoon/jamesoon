# Trading Backend Storage Design

## Executive Summary

**Selected Solution: DynamoDB with On-Demand Pricing**

**Estimated Monthly Cost: $0.00 - $0.50** (FREE for typical usage under AWS free tier)

---

## Requirements Analysis

The trading application needs to persist:

1. **User Profiles**: username, cash balance, initial balance
2. **Portfolio**: stock positions (ticker, shares, average price, current price)
3. **Transactions**: trade history (type, ticker, shares, price, date)

**Access Patterns**:
- Read user profile on login
- Read/update portfolio on trades
- Write new transactions
- Read transaction history (paginated)
- Low traffic: ~100-500 requests/day

---

## Storage Options Evaluated

### Option 1: Amazon DynamoDB (On-Demand) ✅ SELECTED

**Architecture**:
- Single table design: `TradingApp`
- Partition Key: `userId`
- Sort Key: `itemType` (PROFILE | PORTFOLIO#{ticker} | TRANSACTION#{timestamp})

**Pros**:
- **Serverless**: No infrastructure to manage
- **Pay-per-request**: Only pay for actual usage
- **Free tier**: 25 GB storage + 25 WCU + 25 RCU per month (forever)
- **Fast**: Single-digit millisecond latency
- **Scalable**: Auto-scales from zero to millions of requests

**Cons**:
- NoSQL: Different query patterns vs SQL
- Learning curve if unfamiliar with DynamoDB

**Cost Breakdown**:
```
Assumptions:
- 500 requests/day = 15,000 requests/month
- 10 KB average item size
- 100 KB total storage

Storage: 0.1 GB × $0.25/GB = $0.025/month
Reads: 10,000 reads × $0.25/million = $0.0025/month
Writes: 5,000 writes × $1.25/million = $0.00625/month

Total: $0.03/month (likely $0 under free tier)
```

**Free Tier Coverage**:
- 25 GB storage: ✅ Covers 100 KB easily
- 25 RCU/WCU: ✅ Covers ~2.2M requests/month
- Result: **FREE for this use case**

---

### Option 2: Amazon RDS (MySQL/PostgreSQL)

**Architecture**:
- Smallest instance: `db.t4g.micro` (1 vCPU, 1 GB RAM)
- Tables: `users`, `portfolio`, `transactions`

**Pros**:
- Familiar SQL syntax
- ACID transactions
- Complex queries support

**Cons**:
- **Always-on cost**: Even when not used
- Over-provisioned for low traffic
- Requires maintenance (backups, updates)

**Cost**:
```
db.t4g.micro instance: $12.48/month (on-demand)
Storage (20 GB): $2.30/month
Total: ~$14.78/month minimum
```

**Verdict**: ❌ Too expensive for intermittent usage

---

### Option 3: Amazon Aurora Serverless v2

**Architecture**:
- Auto-scaling MySQL/PostgreSQL
- Scales down to 0.5 ACU when idle

**Pros**:
- Serverless (scales to zero)
- SQL compatibility
- High performance

**Cons**:
- Expensive minimum capacity
- Cold start delays

**Cost**:
```
Minimum: 0.5 ACU × $0.12/ACU-hour × 730 hours = $43.80/month
Plus storage: $0.10/GB-month
Total: ~$44+/month
```

**Verdict**: ❌ Way too expensive for this use case

---

### Option 4: Amazon S3 + JSON Files

**Architecture**:
- Store user data as JSON files: `s3://bucket/users/{username}.json`

**Pros**:
- Ultra-cheap storage: $0.023/GB/month
- Simple to implement

**Cons**:
- No ACID guarantees
- Race conditions on concurrent writes
- Must read/write entire file
- No querying capabilities

**Cost**:
```
Storage: 0.001 GB × $0.023/GB = $0.000023/month
PUT requests: 500/month × $0.005/1000 = $0.0025/month
GET requests: 1000/month × $0.0004/1000 = $0.0004/month
Total: ~$0.003/month
```

**Verdict**: ❌ Cheapest but poor fit for transactional data

---

## Final Decision Matrix

| Option | Monthly Cost | Latency | Scalability | Complexity | Data Safety |
|--------|--------------|---------|-------------|------------|-------------|
| **DynamoDB** | **$0-0.50** | < 10ms | Excellent | Low | Excellent |
| RDS | $15+ | < 50ms | Manual | Medium | Excellent |
| Aurora Serverless | $44+ | < 50ms | Auto | Medium | Excellent |
| S3 + JSON | $0.003 | 50-200ms | N/A | High | Poor |

---

## Implementation Details

### DynamoDB Schema

**Table: `TradingApp`**

```
PK (Partition Key): userId (String)
SK (Sort Key): itemType (String)
```

**Item Types**:

1. **User Profile**:
```json
{
  "userId": "user",
  "itemType": "PROFILE",
  "cashBalance": 100000,
  "initialBalance": 100000,
  "createdAt": "2025-11-30T10:00:00Z"
}
```

2. **Portfolio Item**:
```json
{
  "userId": "user",
  "itemType": "PORTFOLIO#AAPL",
  "ticker": "AAPL",
  "shares": 10,
  "averagePrice": 150.50,
  "currentPrice": 155.00,
  "updatedAt": "2025-11-30T10:30:00Z"
}
```

3. **Transaction**:
```json
{
  "userId": "user",
  "itemType": "TRANSACTION#2025-11-30T10:30:00Z",
  "transactionId": "2025-11-30T10:30:00Z_AAPL",
  "ticker": "AAPL",
  "type": "BUY",
  "shares": 10,
  "price": 150.50,
  "total": 1505.00,
  "date": "2025-11-30T10:30:00Z"
}
```

### Access Patterns

1. **Get User Profile**:
   - `GetItem(PK=user, SK=PROFILE)`

2. **Get Portfolio**:
   - `Query(PK=user, SK begins_with PORTFOLIO#)`

3. **Get Transactions** (latest 50):
   - `Query(PK=user, SK begins_with TRANSACTION#, Limit=50, ScanIndexForward=false)`

4. **Buy Stock**:
   - Update/Create portfolio item
   - Update cash balance
   - Insert transaction

5. **Sell Stock**:
   - Update portfolio item (or delete if shares=0)
   - Update cash balance
   - Insert transaction

---

## Infrastructure Components

### 1. DynamoDB Table
- **Name**: `TradingApp`
- **Billing**: On-Demand
- **Keys**: PK=userId, SK=itemType
- **Tags**: Project=SUTD-PRML, Environment=Production

### 2. Lambda Function
- **Name**: `trading-backend`
- **Runtime**: Python 3.11
- **Memory**: 256 MB
- **Timeout**: 30 seconds
- **Environment**: `DYNAMODB_TABLE=TradingApp`

### 3. IAM Role
- **Name**: `lambda-trading-role`
- **Policies**:
  - `AWSLambdaBasicExecutionRole` (CloudWatch Logs)
  - Custom DynamoDB policy (GetItem, PutItem, UpdateItem, DeleteItem, Query)

### 4. API Gateway
- **Type**: HTTP API
- **Name**: `trading-api`
- **CORS**: Enabled for all origins
- **Routes**:
  - `GET /api/trading/health`
  - `GET /api/trading/profile`
  - `GET /api/trading/portfolio`
  - `GET /api/trading/transactions`
  - `POST /api/trading/buy`
  - `POST /api/trading/sell`
  - `POST /api/trading/sync`

---

## API Endpoints

### GET /api/trading/health
Health check endpoint.

**Response**:
```json
{
  "status": "healthy",
  "service": "trading-api"
}
```

### GET /api/trading/profile
Get user profile (creates if doesn't exist).

**Request Body**:
```json
{
  "username": "user"
}
```

**Response**:
```json
{
  "userId": "user",
  "cashBalance": 98500,
  "initialBalance": 100000
}
```

### GET /api/trading/portfolio
Get user's portfolio.

**Request Body**:
```json
{
  "username": "user"
}
```

**Response**:
```json
{
  "portfolio": [
    {
      "ticker": "AAPL",
      "shares": 10,
      "averagePrice": 150.50,
      "currentPrice": 155.00
    }
  ]
}
```

### GET /api/trading/transactions
Get transaction history (latest 50).

**Request Body**:
```json
{
  "username": "user"
}
```

**Response**:
```json
{
  "transactions": [
    {
      "id": "2025-11-30T10:30:00Z_AAPL",
      "ticker": "AAPL",
      "type": "BUY",
      "shares": 10,
      "price": 150.50,
      "total": 1505.00,
      "date": "2025-11-30T10:30:00Z"
    }
  ]
}
```

### POST /api/trading/buy
Execute a buy order.

**Request Body**:
```json
{
  "username": "user",
  "ticker": "AAPL",
  "shares": 10,
  "price": 150.50
}
```

**Response**:
```json
{
  "success": true,
  "newBalance": 98500,
  "message": "Bought 10 shares of AAPL"
}
```

### POST /api/trading/sell
Execute a sell order.

**Request Body**:
```json
{
  "username": "user",
  "ticker": "AAPL",
  "shares": 5,
  "price": 155.00
}
```

**Response**:
```json
{
  "success": true,
  "newBalance": 99275,
  "message": "Sold 5 shares of AAPL"
}
```

### POST /api/trading/sync
Full data sync (backup/restore).

**Request Body**:
```json
{
  "username": "user",
  "profile": {
    "cashBalance": 98000,
    "initialBalance": 100000
  },
  "portfolio": [...],
  "transactions": [...]
}
```

**Response**:
```json
{
  "success": true,
  "message": "Data synced"
}
```

---

## Deployment

### Deploy Backend
```bash
./scripts/08_deploy_trading_backend.sh
```

This script:
1. Creates DynamoDB table
2. Sets up IAM roles and policies
3. Packages and deploys Lambda function
4. Configures API Gateway
5. Saves configuration to `config/trading_api.txt`

### Test Backend
```bash
./scripts/08.1_test_trading_api.sh
```

Runs comprehensive tests:
- Health checks
- User profile operations
- Portfolio CRUD
- Buy/sell transactions
- Error handling
- Infrastructure validation

### Update Frontend
```bash
# Configuration is automatically loaded from config/trading_api.txt
./scripts/09_build_and_deploy_frontend.sh
```

---

## Security Considerations

### Current Implementation (MVP)
- Username passed in request body (no authentication)
- CORS: Allow all origins (*)
- No encryption at rest (DynamoDB default)

### Production Recommendations
1. **Authentication**: Integrate AWS Cognito or JWT tokens
2. **Authorization**: IAM policies per user
3. **CORS**: Restrict to specific domains
4. **Encryption**: Enable DynamoDB encryption at rest
5. **API Key**: Require API key for requests
6. **Rate Limiting**: Add throttling to API Gateway

---

## Monitoring & Operations

### CloudWatch Metrics
- Lambda invocations, duration, errors
- DynamoDB read/write capacity usage
- API Gateway 4xx/5xx errors

### Logs
- Lambda logs: `/aws/lambda/trading-backend`
- View live: `aws logs tail /aws/lambda/trading-backend --follow`

### Cost Tracking
- Enable Cost Explorer in AWS Console
- Tag resources: `Project=SUTD-PRML`
- Set billing alerts for > $1/month

---

## Scalability

**Current Capacity (Free Tier)**:
- 25 WCU + 25 RCU = ~2.2M requests/month
- 25 GB storage

**If Traffic Grows**:
- DynamoDB auto-scales (no config needed)
- Lambda auto-scales (up to account limits)
- Cost remains proportional to usage

**10x Growth Scenario** (5,000 requests/day):
- 150,000 requests/month
- Still within free tier: $0/month

**100x Growth Scenario** (50,000 requests/day):
- 1.5M requests/month
- Estimated cost: ~$3/month

---

## Disaster Recovery

### Backup Strategy
1. **DynamoDB Point-in-Time Recovery**: Enable for 35-day rollback
   - Cost: ~$2.50/month for 10 GB table
2. **On-Demand Backups**: Manual snapshots before major changes
3. **Export to S3**: Periodic full exports for long-term archival

### Restore Procedures
1. **Recent changes** (< 35 days): Use point-in-time recovery
2. **Complete reset**: Restore from S3 export
3. **User data loss**: Contact support with backup ID

---

## Future Enhancements

1. **Real-time Price Updates**: WebSocket API for live stock prices
2. **User Authentication**: AWS Cognito integration
3. **Multi-user Support**: Proper user isolation
4. **Advanced Queries**: GSI for ticker-based queries
5. **Analytics**: DynamoDB Streams → Lambda → Kinesis for real-time analytics
6. **Caching**: DAX (DynamoDB Accelerator) for < 1ms reads (if needed)

---

## Conclusion

**DynamoDB with on-demand pricing** is the optimal choice for this trading application:

✅ **Lowest Cost**: FREE under AWS free tier  
✅ **Best Performance**: < 10ms latency  
✅ **Zero Maintenance**: Fully managed, auto-scaling  
✅ **Production Ready**: Reliable, durable, secure  

Total infrastructure cost: **$0.00/month** for typical usage.

