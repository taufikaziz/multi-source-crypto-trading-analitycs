#!/bin/bash
# MinIO bucket initialization script
# Run automatically when MinIO container starts

mc alias set local http://localhost:9000 minioadmin minioadmin

# Create bucket if not exists
mc mb local/indodax-data || echo "Bucket indodax-data already exists"

# Set bucket policy to public-read (optional, for local dev)
mc anonymous set download local/indodax-data

echo "MinIO bucket initialization complete"