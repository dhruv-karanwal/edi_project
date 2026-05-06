import json
import time
from typing import Dict, List, Any
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import uuid

API_BASE = "http://localhost:8000/api"


def _http_get_json(url: str, timeout: int = 30) -> Any:
    request = Request(url=url, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} GET {url}: {body}") from e
    except URLError as e:
        raise RuntimeError(f"Network error GET {url}: {e}") from e


def _http_post_json(url: str, payload: Dict[str, Any], timeout: int = 180) -> Any:
    data = json.dumps(payload).encode("utf-8")
    request = Request(
        url=url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"}
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} POST {url}: {body}") from e
    except URLError as e:
        raise RuntimeError(f"Network error POST {url}: {e}") from e


def _http_delete(url: str, timeout: int = 30) -> Any:
    request = Request(url=url, method="DELETE")
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {"ok": True}
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} DELETE {url}: {body}") from e
    except URLError as e:
        raise RuntimeError(f"Network error DELETE {url}: {e}") from e


def _http_post_multipart_file(
    url: str,
    file_path: Path,
    field_name: str = "file",
    timeout: int = 180
) -> Any:
    boundary = f"----ResearchRagBoundary{uuid.uuid4().hex}"
    file_bytes = file_path.read_bytes()

    body = bytearray()
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(
        f'Content-Disposition: form-data; name="{field_name}"; filename="{file_path.name}"\r\n'.encode("utf-8")
    )
    body.extend(b"Content-Type: application/pdf\r\n\r\n")
    body.extend(file_bytes)
    body.extend(f"\r\n--{boundary}--\r\n".encode("utf-8"))

    request = Request(
        url=url,
        data=bytes(body),
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} POST {url}: {body_text}") from e
    except URLError as e:
        raise RuntimeError(f"Network error POST {url}: {e}") from e

def ask_question(document_id: str, question: str) -> Dict[str, Any]:
    return _http_post_json(
        f"{API_BASE}/query/ask",
        {
            "document_id": document_id,
            "question": question
        },
        timeout=180
    )

def list_documents() -> List[Dict[str, Any]]:
    data = _http_get_json(f"{API_BASE}/documents", timeout=30)
    if not isinstance(data, list):
        raise ValueError("Unexpected /documents response format")
    return data


def upload_document(file_path: Path) -> Dict[str, Any]:
    return _http_post_multipart_file(f"{API_BASE}/ingest/upload", file_path, timeout=300)


def get_upload_status(document_id: str) -> Dict[str, Any]:
    data = _http_get_json(f"{API_BASE}/ingest/status/{document_id}", timeout=30)
    if not isinstance(data, dict):
        raise ValueError("Unexpected /ingest/status response format")
    return data


def delete_document(document_id: str) -> Dict[str, Any]:
    data = _http_delete(f"{API_BASE}/documents/{document_id}", timeout=60)
    if not isinstance(data, dict):
        return {"message": "deleted"}
    return data

def find_document_id_by_filename(filename: str) -> str:
    documents = list_documents()
    for doc in documents:
        if doc["filename"] == filename and doc["status"] == "ready":
            return doc["id"]
    raise ValueError(f"Ready document not found for filename: {filename}")

def answer_contains_expected(answer: str, expected_terms: List[str]) -> float:
    if not expected_terms:
        return 1.0
    answer_lower = answer.lower()
    hits = sum(1 for term in expected_terms if term.lower() in answer_lower)
    return hits / len(expected_terms)

def evidence_page_precision(evidence: List[Dict[str, Any]], expected_pages: List[int]) -> float:
    if not evidence:
        return 0.0
    if not expected_pages:
        return 1.0
    hits = sum(1 for ev in evidence if ev["page_number"] in expected_pages)
    return hits / len(evidence)

def evidence_type_precision(evidence: List[Dict[str, Any]], expected_types: List[str]) -> float:
    if not evidence:
        return 0.0
    if not expected_types:
        return 1.0
    hits = sum(1 for ev in evidence if ev["chunk_type"] in expected_types)
    return hits / len(evidence)

def run_eval(dataset_path: str):
    dataset_file = Path(dataset_path)
    if not dataset_file.exists():
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")

    raw = dataset_file.read_text(encoding="utf-8-sig").strip()
    if not raw:
        print(json.dumps({
            "num_examples": 0,
            "num_successful": 0,
            "avg_latency_sec": None,
            "avg_answer_term_match": None,
            "avg_evidence_page_precision": None,
            "avg_evidence_type_precision": None,
            "results": [],
            "warning": f"Dataset file is empty: {dataset_path}"
        }, indent=2))
        return

    dataset = json.loads(raw)
    if not isinstance(dataset, list):
        raise ValueError("Dataset JSON must be an array of evaluation items")

    results = []
    for i, item in enumerate(dataset, 1):
        filename = item["document_filename"]
        question = item["question"]
        expected_terms = item.get("expected_answer_contains", [])
        expected_pages = item.get("expected_pages", [])
        expected_types = item.get("expected_chunk_types", [])

        try:
            document_id = find_document_id_by_filename(filename)
        except Exception as e:
            results.append({
                "index": i,
                "question": question,
                "error": f"document lookup failed: {e}"
            })
            continue

        start = time.time()
        try:
            response = ask_question(document_id, question)
            latency = time.time() - start

            answer_score = answer_contains_expected(
                response["answer"],
                expected_terms
            )
            page_precision = evidence_page_precision(
                response.get("evidence", []),
                expected_pages
            )
            type_precision = evidence_type_precision(
                response.get("evidence", []),
                expected_types
            )

            results.append({
                "index": i,
                "question": question,
                "latency_sec": round(latency, 2),
                "answer_term_match": round(answer_score, 3),
                "evidence_page_precision": round(page_precision, 3),
                "evidence_type_precision": round(type_precision, 3),
                "answer": response["answer"][:500],
                "evidence_count": len(response.get("evidence", []))
            })

        except Exception as e:
            results.append({
                "index": i,
                "question": question,
                "error": str(e)
            })

    valid_results = [r for r in results if "error" not in r]
    summary = {
        "num_examples": len(dataset),
        "num_successful": len(valid_results),
        "avg_latency_sec": round(
            sum(r["latency_sec"] for r in valid_results) / len(valid_results), 2
        ) if valid_results else None,
        "avg_answer_term_match": round(
            sum(r["answer_term_match"] for r in valid_results) / len(valid_results), 3
        ) if valid_results else None,
        "avg_evidence_page_precision": round(
            sum(r["evidence_page_precision"] for r in valid_results) / len(valid_results), 3
        ) if valid_results else None,
        "avg_evidence_type_precision": round(
            sum(r["evidence_type_precision"] for r in valid_results) / len(valid_results), 3
        ) if valid_results else None,
        "results": results
    }

    print(json.dumps(summary, indent=2))


def run_ingestion_eval(
    file_paths: List[Path],
    poll_interval_sec: float = 2.0,
    timeout_sec: int = 1800,
    cleanup_uploaded: bool = False,
):
    results = []

    for i, file_path in enumerate(file_paths, 1):
        if not file_path.exists() or not file_path.is_file():
            results.append({
                "index": i,
                "file": str(file_path),
                "error": "file not found"
            })
            continue

        if file_path.suffix.lower() != ".pdf":
            results.append({
                "index": i,
                "file": str(file_path),
                "error": "not a pdf"
            })
            continue

        overall_start = time.time()
        try:
            upload_response = upload_document(file_path)
            document_id = upload_response["document_id"]
            upload_ack_latency = time.time() - overall_start
        except Exception as e:
            results.append({
                "index": i,
                "file": str(file_path),
                "error": f"upload failed: {e}"
            })
            continue

        final_status = None
        status_payload = None
        deadline = overall_start + timeout_sec
        polls = 0

        while time.time() < deadline:
            polls += 1
            status_payload = get_upload_status(document_id)
            final_status = status_payload.get("status")

            if final_status in {"ready", "failed"}:
                break

            time.sleep(poll_interval_sec)

        total_time = time.time() - overall_start

        item = {
            "index": i,
            "file": str(file_path),
            "filename": file_path.name,
            "document_id": document_id,
            "upload_ack_sec": round(upload_ack_latency, 2),
            "processing_sec": round(total_time, 2),
            "poll_count": polls,
            "status": final_status or "timeout",
            "page_count": status_payload.get("page_count") if status_payload else None,
            "error_message": status_payload.get("error_message") if status_payload else None,
        }

        if cleanup_uploaded and document_id:
            try:
                delete_document(document_id)
                item["cleanup"] = "deleted"
            except Exception as e:
                item["cleanup"] = f"delete failed: {e}"

        results.append(item)

    completed = [r for r in results if "error" not in r and r.get("status") == "ready"]
    summary = {
        "num_files": len(file_paths),
        "num_ready": len(completed),
        "avg_processing_sec": round(
            sum(r["processing_sec"] for r in completed) / len(completed), 2
        ) if completed else None,
        "min_processing_sec": min((r["processing_sec"] for r in completed), default=None),
        "max_processing_sec": max((r["processing_sec"] for r in completed), default=None),
        "results": results,
    }

    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        type=str,
        default="qa",
        choices=["qa", "ingestion", "all"],
        help="Evaluation mode: qa, ingestion, or all"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="evaluation/eval_dataset.json",
        help="Path to evaluation dataset JSON"
    )
    parser.add_argument(
        "--upload-files",
        nargs="*",
        default=[],
        help="PDF file paths for ingestion benchmarking"
    )
    parser.add_argument(
        "--upload-dir",
        type=str,
        default="",
        help="Directory containing PDFs for ingestion benchmarking"
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Polling interval in seconds for ingestion status"
    )
    parser.add_argument(
        "--ingestion-timeout",
        type=int,
        default=1800,
        help="Timeout in seconds per PDF ingestion"
    )
    parser.add_argument(
        "--cleanup-uploaded",
        action="store_true",
        help="Delete uploaded documents after ingestion benchmark"
    )
    args = parser.parse_args()

    upload_candidates: List[Path] = [Path(p) for p in args.upload_files]
    if args.upload_dir:
        upload_candidates.extend(sorted(Path(args.upload_dir).glob("*.pdf")))

    # Keep order but deduplicate
    seen = set()
    upload_files: List[Path] = []
    for p in upload_candidates:
        key = str(p.resolve()) if p.exists() else str(p)
        if key not in seen:
            seen.add(key)
            upload_files.append(p)

    if args.mode in {"qa", "all"}:
        run_eval(args.dataset)

    if args.mode in {"ingestion", "all"}:
        if not upload_files:
            raise ValueError(
                "No PDFs provided for ingestion mode. Use --upload-files and/or --upload-dir."
            )
        run_ingestion_eval(
            file_paths=upload_files,
            poll_interval_sec=args.poll_interval,
            timeout_sec=args.ingestion_timeout,
            cleanup_uploaded=args.cleanup_uploaded,
        )