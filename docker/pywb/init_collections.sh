#!/bin/bash

# Initialize pywb collections for crypto analytics archival system
# This script sets up the main collection structure

set -e

COLLECTIONS_DIR="/webarchive/collections"
COLLECTION_NAME="crypto_projects"

echo "Initializing pywb collections..."

# Create collections directory if it doesn't exist
mkdir -p "$COLLECTIONS_DIR"

# Create main collection
if [ ! -d "$COLLECTIONS_DIR/$COLLECTION_NAME" ]; then
    echo "Creating collection: $COLLECTION_NAME"
    wb-manager init "$COLLECTION_NAME"
    echo "✓ Collection $COLLECTION_NAME created"
else
    echo "✓ Collection $COLLECTION_NAME already exists"
fi

# Create indexes directory structure
mkdir -p "$COLLECTIONS_DIR/$COLLECTION_NAME/indexes"
mkdir -p "$COLLECTIONS_DIR/$COLLECTION_NAME/archive"

# Link to WARC storage (if using symlinks instead of direct paths)
# ln -sf /warcs/raw "$COLLECTIONS_DIR/$COLLECTION_NAME/archive/warcs"
# ln -sf /warcs/cdx "$COLLECTIONS_DIR/$COLLECTION_NAME/indexes/cdx"

echo "✓ Collection initialization complete"
echo ""
echo "Collection structure:"
tree -L 2 "$COLLECTIONS_DIR" || ls -lR "$COLLECTIONS_DIR"

echo ""
echo "pywb is ready to serve archives!"
echo "Access the replay UI at: http://localhost:8080"
