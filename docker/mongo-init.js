// Mongo init script for local Phase1 development
// This file is executed once when the MongoDB container initializes
// (docker-entrypoint-initdb.d hook).

// Use application DB
db = db.getSiblingDB("sentencify");

// --- correction_history (D) ---
if (!db.getCollectionNames().includes("correction_history")) {
  db.createCollection("correction_history");
}
db.correction_history.createIndex({ user: 1, created_at: -1 });
db.correction_history.createIndex({ field: 1, created_at: -1 });
db.correction_history.createIndex({ intensity: 1 });

// --- full_document_store (K) ---
if (!db.getCollectionNames().includes("full_document_store")) {
  db.createCollection("full_document_store");
}
db.full_document_store.createIndex({ doc_id: 1 }, { unique: true });
db.full_document_store.createIndex({ last_synced_at: -1 });

// --- optional: usage_summary (기업 1번) ---
if (!db.getCollectionNames().includes("usage_summary")) {
  db.createCollection("usage_summary");
}
db.usage_summary.createIndex({ recent_execution_date: -1 });
db.usage_summary.createIndex({ count: -1 });

// --- optional: client_properties (기업 2번) ---
if (!db.getCollectionNames().includes("client_properties")) {
  db.createCollection("client_properties");
}
db.client_properties.createIndex({ "properties.last_seen": -1 });
db.client_properties.createIndex({ distinct_id: 1 }, { unique: true });

// --- optional: event_raw (기업 3번) ---
if (!db.getCollectionNames().includes("event_raw")) {
  db.createCollection("event_raw");
}
db.event_raw.createIndex({ event: 1, time: -1 });
db.event_raw.createIndex({ insert_id: 1 }, { unique: true });
db.event_raw.createIndex({ user_id: 1, time: -1 });

// --- users (회원 관리용) ---
if (!db.getCollectionNames().includes("users")) {
  db.createCollection("users");
}
db.users.createIndex({ email: 1 }, { unique: true });

// --- simple metadata record for debugging ---
if (!db.metadata) {
  db.createCollection("metadata");
}
db.metadata.insertOne({
  type: "init",
  source: "docker-entrypoint-initdb.d/mongo-init.js",
  created_at: new Date(),
  note: "Phase1 base collections and indexes initialized.",
});
