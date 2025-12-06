#!/bin/bash

# Exit on error
set -e

# --- CONFIGURATION ---
# The domain you own and have registered with a registrar like Namecheap.
# IMPORTANT: Do not include 'www' or any other subdomain here.
DOMAIN_NAME="mdaie-sutd.fit"

# The subdomain you want to point to your CloudFront distribution (e.g., 'www', 'app', 'mdaie-prml').
HOSTNAME="prml"

# --- SCRIPT ---
AWS_REGION="ap-southeast-1"
CLOUDFRONT_DISTRIBUTION_ID=$(aws cloudfront list-distributions --query "DistributionList.Items[?contains(Origins.Items[0].DomainName, 'ml-model-frontend')].Id" --output text | head -n 1 | awk '{print $1}')
CLOUDFRONT_DOMAIN_NAME=$(aws cloudfront get-distribution --id $CLOUDFRONT_DISTRIBUTION_ID --query "Distribution.DomainName" --output text)

if [ -z "$CLOUDFRONT_DISTRIBUTION_ID" ] || [ -z "$CLOUDFRONT_DOMAIN_NAME" ]; then
    echo "Error: Could not find a CloudFront distribution for the frontend S3 bucket."
    echo "Please run the '06_setup_cloudfront.sh' script first."
    exit 1
fi

echo "Found CloudFront Distribution:"
echo "ID: $CLOUDFRONT_DISTRIBUTION_ID"
echo "Domain: $CLOUDFRONT_DOMAIN_NAME"
echo ""

echo "Step 1: Checking for/Creating Hosted Zone for $DOMAIN_NAME..."

# Check if hosted zone already exists
HOSTED_ZONE_ID=$(aws route53 list-hosted-zones-by-name --dns-name "$DOMAIN_NAME" --query "HostedZones[0].Id" --output text | sed 's/^\/hostedzone\///' || true)

if [ -z "$HOSTED_ZONE_ID" ]; then
    # Create a unique caller reference for the hosted zone creation
    CALLER_REFERENCE=$(date +%s)
    
    echo "Creating new Hosted Zone for $DOMAIN_NAME..."
    HOSTED_ZONE_INFO=$(aws route53 create-hosted-zone --name "$DOMAIN_NAME" --caller-reference "$CALLER_REFERENCE")
    HOSTED_ZONE_ID=$(echo "$HOSTED_ZONE_INFO" | jq -r '.HostedZone.Id' | sed 's/^\/hostedzone\///')
    NAMESERVERS=$(echo "$HOSTED_ZONE_INFO" | jq -r '.DelegationSet.NameServers[]')
    
    echo "Hosted Zone ID: $HOSTED_ZONE_ID"
    echo ""
    echo "------------------------------------------------------------------"
    echo "IMPORTANT ACTION REQUIRED:"
    echo "Log in to your domain registrar (e.g., Namecheap) and set the"
    echo "following 'Custom DNS' nameservers for '$DOMAIN_NAME':"
    echo ""
    echo "$NAMESERVERS"
    echo ""
    echo "DNS propagation may take some time. Please ensure this is done."
    echo "------------------------------------------------------------------"
    echo ""
else
    echo "Hosted Zone for $DOMAIN_NAME already exists. ID: $HOSTED_ZONE_ID"
    # Get nameservers if zone already exists, for informational purposes
    NAMESERVERS=$(aws route53 get-hosted-zone --id "$HOSTED_ZONE_ID" --query 'HostedZone.NameServers[]' --output text)
    echo "Existing Nameservers: $NAMESERVERS"
fi

echo "Step 2: Checking for/Creating Alias record for $HOSTNAME.$DOMAIN_NAME to CloudFront..."

# CloudFront has a fixed Hosted Zone ID for all distributions
# See: https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/resource-record-sets-values-alias.html
CLOUDFRONT_HOSTED_ZONE_ID="Z2FDTNDATAQYW2"

# Check if the Alias record already exists
RECORD_EXISTS=$(aws route53 list-resource-record-sets \
  --hosted-zone-id "$HOSTED_ZONE_ID" \
  --query "ResourceRecordSets[?Name == '$HOSTNAME.$DOMAIN_NAME.' && Type == 'A'].Name" \
  --output text || true)

if [ -z "$RECORD_EXISTS" ]; then
    echo "Creating Alias record for $HOSTNAME.$DOMAIN_NAME..."
    # Create the JSON for the record set change
    CHANGE_BATCH_JSON=$(cat <<EOF
{
  "Comment": "Create Alias record for CloudFront distribution",
  "Changes": [
    {
      "Action": "CREATE",
      "ResourceRecordSet": {
        "Name": "$HOSTNAME.$DOMAIN_NAME",
        "Type": "A",
        "AliasTarget": {
          "HostedZoneId": "$CLOUDFRONT_HOSTED_ZONE_ID",
          "DNSName": "$CLOUDFRONT_DOMAIN_NAME",
          "EvaluateTargetHealth": false
        }
      }
    }
  ]
}
EOF
    )

    # Create the resource record set
    aws route53 change-resource-record-sets \
      --hosted-zone-id "$HOSTED_ZONE_ID" \
      --change-batch "$CHANGE_BATCH_JSON"

    echo ""
    echo "Successfully created Alias record."
    echo "Once DNS propagation is complete, you should be able to access your application at:"
    echo "https://$HOSTNAME.$DOMAIN_NAME"
else
    echo "Alias record for $HOSTNAME.$DOMAIN_NAME already exists."
    echo "You should be able to access your application at: https://$HOSTNAME.$DOMAIN_NAME"
fi

echo ""
echo "Route 53 setup complete."
