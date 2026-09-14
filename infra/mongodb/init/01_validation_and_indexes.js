// MongoDB validation and indexes for indodax database
// ==============================================================================
// This script runs automatically when the container is first created.
// It sets up validation rules for event envelope structure and creates indexes.
// ==============================================================================

use(${process.env.MONGO_INITDB_DATABASE});

// ------------------------------------------------------------------------------
// 1. Orderbooks Collection Validation
// ------------------------------------------------------------------------------
db.createCollection("orderbooks", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["event", "context", "ingested_at"],
      properties: {
        event: {
          bsonType: "string",
          description: "Event type is required and must be a string"
        },
        context: {
          bsonType: "object",
          description: "Context payload is required and must be an object"
        },
        ingested_at: {
          bsonType: "string",
          pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}",
          description: "Ingestion timestamp in ISO8601 format is required"
        }
      }
    }
  },
  validationLevel: "moderate",
  validationAction: "warn"
});

// Indexes for orderbooks
db.orderbooks.createIndex({ "event": 1 });
db.orderbooks.createIndex({ "context.pair": 1 });
db.orderbooks.createIndex({ "ingested_at": -1 });
db.orderbooks.createIndex({ "ingested_at": -1, "context.pair": 1 });

// ------------------------------------------------------------------------------
// 2. Tickers Collection Validation
// ------------------------------------------------------------------------------
db.createCollection("tickers", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["event", "context", "ingested_at"],
      properties: {
        event: {
          bsonType: "string",
          description: "Event type is required and must be a string"
        },
        context: {
          bsonType: "object",
          description: "Context payload is required and must be an object"
        },
        ingested_at: {
          bsonType: "string",
          pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}",
          description: "Ingestion timestamp in ISO8601 format is required"
        }
      }
    }
  },
  validationLevel: "moderate",
  validationAction: "warn"
});

// Indexes for tickers
db.tickers.createIndex({ "event": 1 });
db.tickers.createIndex({ "context.pair": 1 });
db.tickers.createIndex({ "ingested_at": -1 });
db.tickers.createIndex({ "ingested_at": -1, "context.pair": 1 });

// ------------------------------------------------------------------------------
// 3. User Events Collection (no strict schema, only envelope validation)
// ------------------------------------------------------------------------------
db.createCollection("user_events", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["event_type", "context", "ingested_at"],
      properties: {
        event_type: {
          bsonType: "string",
          description: "Event type is required"
        },
        context: {
          bsonType: "object",
          description: "Context payload is required"
        },
        ingested_at: {
          bsonType: "string",
          pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}",
          description: "Ingestion timestamp in ISO8601 format is required"
        }
      }
    }
  },
  validationLevel: "moderate",
  validationAction: "warn"
});

// Indexes for user_events
db.user_events.createIndex({ "event_type": 1 });
db.user_events.createIndex({ "ingested_at": -1 });
db.user_events.createIndex({ "ingested_at": -1, "event_type": 1 });
