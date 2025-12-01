import json
import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

from kafka import KafkaConsumer
from pymongo import MongoClient

from app.schemas.corporate import CorporateRunLog, CorporateSelectLog, CorrectionHistory
from app.schemas.logs import LogA, LogB, LogC, LogI
from app.utils.embedding import get_embedding
from app.qdrant.service import insert_point

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "sentencify")
BATCH_MAX_SIZE = int(os.getenv("CONSUMER_BATCH_SIZE", "100"))
BATCH_FLUSH_INTERVAL = float(os.getenv("CONSUMER_BATCH_INTERVAL", "1.0"))
KAFKA_TOPICS = [
    "editor_run_paraphrasing",
    "editor_selected_paraphrasing",
    "editor_recommend_options",
    "recommend_log",
    "editor_document_snapshot",
    "context_block",
]


class BatchProcessor:
    def __init__(self, collection, name: str, max_size: int, flush_interval: float):
        self.collection = collection
        self.name = name
        self.max_size = max_size
        self.flush_interval = flush_interval
        self._buffer: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._last_flush = time.time()

    def add(self, doc: Any) -> None:
        if doc is None:
            return
        if hasattr(doc, "model_dump"):
            payload = doc.model_dump()
        else:
            payload = dict(doc)
        with self._lock:
            self._buffer.append(payload)
            should_flush = len(self._buffer) >= self.max_size or (
                time.time() - self._last_flush >= self.flush_interval
            )
            if should_flush:
                self._flush_locked()

    def flush(self, force: bool = False) -> None:
        with self._lock:
            if self._buffer and (force or (time.time() - self._last_flush) >= self.flush_interval):
                self._flush_locked()

    def _flush_locked(self) -> None:
        if not self._buffer:
            return
        docs = self._buffer
        self._buffer = []
        try:
            self.collection.insert_many(docs)
        except Exception as exc:
            print(f"[BatchProcessor:{self.name}] insert_many failed: {exc}")
            self._buffer.extend(docs)
            return
        self._last_flush = time.time()


class SmartRouter:
    def __init__(
        self,
        mongo_client: Optional[MongoClient] = None,
        batch_size: int = BATCH_MAX_SIZE,
        flush_interval: float = BATCH_FLUSH_INTERVAL,
    ):
        self.mongo_client = mongo_client or MongoClient(MONGO_URI)
        self.db = self.mongo_client[MONGO_DB_NAME]
        self.batchers = {
            "corporate_run_logs": BatchProcessor(
                self.db["corporate_run_logs"], "corporate_run_logs", batch_size, flush_interval
            ),
            "corporate_select_logs": BatchProcessor(
                self.db["corporate_select_logs"], "corporate_select_logs", batch_size, flush_interval
            ),
            "correction_history": BatchProcessor(
                self.db["correction_history"], "correction_history", batch_size, flush_interval
            ),
            "log_a_recommend": BatchProcessor(
                self.db["log_a_recommend"], "log_a_recommend", batch_size, flush_interval
            ),
            "log_b_run": BatchProcessor(self.db["log_b_run"], "log_b_run", batch_size, flush_interval),
            "log_c_select": BatchProcessor(
                self.db["log_c_select"], "log_c_select", batch_size, flush_interval
            ),
            "log_i_meta": BatchProcessor(self.db["log_i_meta"], "log_i_meta", batch_size, flush_interval),
        }
        self.full_document_store = self.db["full_document_store"]

    def _with_base_defaults(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        now_seconds = int(time.time())
        enriched = dict(payload)
        if not enriched.get("distinct_id"):
            fallback = (
                payload.get("user_id")
                or payload.get("device_id")
                or payload.get("doc_id")
                or "anonymous"
            )
            enriched["distinct_id"] = str(fallback)
        insert_source = (
            enriched.get("insert_id") or payload.get("event_id") or str(uuid4())
        )
        enriched["insert_id"] = str(insert_source)
        if not enriched.get("time"):
            enriched["time"] = now_seconds
        if "mp_api_timestamp_ms" not in enriched or enriched["mp_api_timestamp_ms"] is None:
            enriched["mp_api_timestamp_ms"] = int(now_seconds * 1000)
        return enriched

    def handle_payload(self, payload: Dict[str, Any]) -> None:
        event = payload.get("event")
        if event == "editor_run_paraphrasing":
            self._handle_run(payload)
        elif event == "editor_selected_paraphrasing":
            self._handle_select(payload)
        elif event == "editor_recommend_options":
            self._handle_recommend(payload)
        elif event == "recommend_log":
            self._handle_recommend_log(payload)
        elif event == "editor_document_snapshot":
            self._handle_snapshot(payload)
        elif event == "context_block":
            self._handle_context_block(payload)

    def flush_all(self) -> None:
        for processor in self.batchers.values():
            processor.flush(force=True)

    def _handle_run(self, payload: Dict[str, Any]) -> None:
        enriched = self._with_base_defaults(payload)
        enriched.setdefault("llm_name", payload.get("paraphrase_llm_version"))
        enriched.setdefault("maintenance", payload.get("maintenance") or payload.get("target_intensity"))
        enriched.setdefault("field", payload.get("field") or payload.get("target_category"))
        enriched.setdefault(
            "target_language",
            payload.get("target_language") or payload.get("language"),
        )
        if enriched.get("input_sentence_length") is None:
            enriched["input_sentence_length"] = len((payload.get("selected_text") or ""))
        enriched.setdefault("platform", payload.get("platform") or "web")
        enriched.setdefault("trigger", payload.get("trigger") or "editor_run_paraphrasing")
        if payload.get("response_time_ms") is not None:
            enriched["response_time_ms"] = payload.get("response_time_ms")
        log_b_data = dict(enriched)
        log_b_data["source_recommend_event_id"] = payload.get("source_recommend_event_id")
        log_b_data["recommend_session_id"] = payload.get("recommend_session_id")
        run_doc = CorporateRunLog(**enriched)
        log_b = LogB(**log_b_data)
        self.batchers["corporate_run_logs"].add(run_doc)
        self.batchers["log_b_run"].add(log_b)

    def _handle_select(self, payload: Dict[str, Any]) -> None:
        enriched = self._with_base_defaults(payload)
        enriched.setdefault("maintenance", payload.get("maintenance") or payload.get("final_strength"))
        enriched.setdefault("field", payload.get("field") or payload.get("final_category"))
        enriched.setdefault(
            "target_language",
            payload.get("target_language") or payload.get("final_language"),
        )
        log_c_data = dict(enriched)
        log_c_data["source_recommend_event_id"] = payload.get("source_recommend_event_id")
        log_c_data["recommend_session_id"] = payload.get("recommend_session_id")
        log_c_data["was_accepted"] = payload.get("was_accepted")
        select_doc = CorporateSelectLog(**enriched)
        log_c = LogC(**log_c_data)
        self.batchers["corporate_select_logs"].add(select_doc)
        self.batchers["log_c_select"].add(log_c)

        outputs = (
            payload.get("output_sentences")
            or payload.get("paraphrasing_candidates")
            or ([payload.get("selected_candidate_text")] if payload.get("selected_candidate_text") else [])
        )
        correction = CorrectionHistory(
            user=payload.get("user_id"),
            field=enriched.get("field"),
            intensity=enriched.get("maintenance"),
            user_prompt=payload.get("user_prompt"),
            input_sentence=payload.get("input_sentence")
            or payload.get("original_text")
            or payload.get("selected_text"),
            output_sentences=outputs,
            selected_index=payload.get("index"),
        )
        self.batchers["correction_history"].add(correction)

    def _handle_recommend(self, payload: Dict[str, Any]) -> None:
        log_a = LogA(
            insert_id=payload.get("insert_id"),
            recommend_session_id=payload.get("recommend_session_id"),
            user_id=payload.get("user_id"),
            doc_id=payload.get("doc_id"),
            reco_options=payload.get("reco_options") or [],
            P_vec=payload.get("P_vec") or {},
            P_doc=payload.get("P_doc") or {},
            applied_weight_doc=payload.get("applied_weight_doc") or 0.0,
            doc_maturity_score=payload.get("doc_maturity_score") or 0.0,
        )
        self.batchers["log_a_recommend"].add(log_a)

    def _handle_recommend_log(self, payload: Dict[str, Any]) -> None:
        log_i = LogI(
            latency_ms=payload.get("latency_ms"),
            model_version=payload.get("model_version"),
            is_shadow_mode=payload.get("is_shadow_mode"),
        )
        self.batchers["log_i_meta"].add(log_i)

    def _handle_snapshot(self, payload: Dict[str, Any]) -> None:
        doc_id = payload.get("doc_id")
        if not doc_id:
            return
        full_text = payload.get("full_text") or ""
        user_id = payload.get("user_id")
        now = datetime.utcnow().isoformat()
        existing = self.full_document_store.find_one({"doc_id": doc_id})
        if existing:
            prev_text = existing.get("latest_full_text") or ""
            len_prev = len(prev_text)
            len_curr = len(full_text)
            diff_ratio = abs(len_curr - len_prev) / max(len_prev, 1)
            self.full_document_store.update_one(
                {"doc_id": doc_id},
                {
                    "$set": {
                        "previous_full_text": prev_text,
                        "latest_full_text": full_text,
                        "diff_ratio": diff_ratio,
                        "user_id": user_id or existing.get("user_id"),
                        "last_synced_at": now,
                    }
                },
                upsert=True,
            )
        else:
            self.full_document_store.update_one(
                {"doc_id": doc_id},
                {
                    "$set": {
                        "doc_id": doc_id,
                        "user_id": user_id,
                        "latest_full_text": full_text,
                        "previous_full_text": None,
                        "diff_ratio": 1.0,
                        "created_at": now,
                        "last_synced_at": now,
                    }
                },
                upsert=True,
            )

    def _handle_context_block(self, payload: Dict[str, Any]) -> None:
        """E.context_block 이벤트를 처리하여 Qdrant에 저장합니다."""
        context_hash = payload.get("context_hash")
        context_full = payload.get("context_full")

        if not context_hash or not context_full:
            print(f"[ERROR] Invalid context_block event: {payload}")
            return

        try:
            # 1. 텍스트 임베딩 생성
            embedding = get_embedding(context_full)

            # 2. Qdrant에 저장할 payload 구성
            qdrant_payload = {
                "doc_id": payload.get("doc_id"),
                "user_id": payload.get("user_id"),
                "context_full_preview": context_full[:500],
                "created_at": payload.get("created_at"),
            }

            # 3. Qdrant에 데이터 저장
            insert_point(
                point_id=context_hash,
                vector=embedding,
                payload=qdrant_payload
            )
            print(f"[INFO] Successfully inserted context_block with hash: {context_hash[:10]}...")

        except Exception as e:
            print(f"[ERROR] Failed to process context_block event: {e}")


def build_kafka_consumer(topics: Iterable[str]) -> KafkaConsumer:
    return KafkaConsumer(
        *topics,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id="sentencify_phase2_router",
    )


def consume_loop(router: SmartRouter, consumer: KafkaConsumer) -> None:
    try:
        for msg in consumer:
            payload = msg.value
            if isinstance(payload, dict):
                router.handle_payload(payload)
    except KeyboardInterrupt:
        print("[consumer] Interrupted; flushing batches...")
    finally:
        router.flush_all()


class PeriodicFlusher(threading.Thread):
    def __init__(self, router: SmartRouter, interval: float = 1.0):
        super().__init__(daemon=True)
        self.router = router
        self.interval = interval
        self.stop_event = threading.Event()

    def run(self) -> None:
        while not self.stop_event.is_set():
            time.sleep(self.interval)
            self.router.flush_all()

    def stop(self) -> None:
        self.stop_event.set()


def main() -> None:
    router = SmartRouter()
    consumer = build_kafka_consumer(KAFKA_TOPICS)
    flusher = PeriodicFlusher(router, interval=1.0)
    flusher.start()
    try:
        consume_loop(router, consumer)
    finally:
        flusher.stop()


if __name__ == "__main__":
    main()
