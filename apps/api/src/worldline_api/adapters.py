from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

REQUIRED_ADAPTER_METHODS = ("discover", "fetch", "parse", "normalize")
COLLECTION_CHANNEL_DEFINITIONS = [
    {"channel": "web_page", "label": "Web page", "source_type": "public_web", "adapter_source_type": "public_web", "schema_path": "/api/v1/collection-channels/web_page/schema"},
    {"channel": "official_api", "label": "Official API", "source_type": "official_api", "adapter_source_type": "official_api", "schema_path": "/api/v1/collection-channels/official_api/schema"},
    {"channel": "rss", "label": "RSS feed", "source_type": "rss", "adapter_source_type": "rss", "schema_path": "/api/v1/collection-channels/rss/schema"},
    {"channel": "document_file", "label": "Document file", "source_type": "file_upload", "adapter_source_type": "file_upload", "schema_path": "/api/v1/collection-channels/document_file/schema"},
    {"channel": "image_file", "label": "Image file", "source_type": "media", "adapter_source_type": "media", "schema_path": "/api/v1/collection-channels/image_file/schema"},
    {"channel": "video_file", "label": "Video file", "source_type": "media", "adapter_source_type": "media", "schema_path": "/api/v1/collection-channels/video_file/schema"},
    {"channel": "livestream", "label": "Livestream", "source_type": "live_segment", "adapter_source_type": "live_segment", "schema_path": "/api/v1/collection-channels/livestream/schema"},
    {"channel": "audio_file", "label": "Audio file", "source_type": "media", "adapter_source_type": "media", "schema_path": "/api/v1/collection-channels/audio_file/schema"},
    {"channel": "webhook", "label": "Webhook", "source_type": "webhook", "adapter_source_type": "webhook", "schema_path": "/api/v1/collection-channels/webhook/schema"},
    {"channel": "database", "label": "Database", "source_type": "db_import", "adapter_source_type": "db_import", "schema_path": "/api/v1/collection-channels/database/schema"},
    {"channel": "object_storage", "label": "Object storage", "source_type": "object_storage", "adapter_source_type": "object_storage", "schema_path": "/api/v1/collection-channels/object_storage/schema"},
]
COLLECTION_CHANNEL_CONFIG_SCHEMAS = {
    "web_page": {
        "channel": "web_page",
        "label": "Web page",
        "source_type": "public_web",
        "adapter_source_type": "public_web",
        "version": "2026-05-10.at295",
        "status": "ready",
        "schema_kind": "json_schema",
        "required_fields": ["start_url", "max_depth", "respect_robots", "rate_limit_per_minute"],
        "json_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["start_url", "max_depth", "respect_robots", "rate_limit_per_minute"],
            "properties": {
                "start_url": {
                    "type": "string",
                    "format": "uri",
                    "title": "Start URL",
                    "description": "HTTP(S) or synthetic public web seed URL used by crawl policy and link discovery.",
                    "x-accepted-schemes": ["https", "http", "synthetic"],
                },
                "max_depth": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 5,
                    "default": 2,
                    "description": "Maximum link discovery depth from the seed URL.",
                },
                "respect_robots": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether robots-disallowed URLs must be skipped and recorded as skipped evidence.",
                },
                "rate_limit_per_minute": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 120,
                    "default": 30,
                    "description": "Maximum public-web fetch or discovery starts per minute for this source.",
                },
                "allowed_domains": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [],
                    "description": "Optional domain allowlist for discovered child links.",
                },
            },
        },
        "ui_schema": {
            "field_order": ["start_url", "max_depth", "respect_robots", "rate_limit_per_minute", "allowed_domains"],
            "fields": [
                {"name": "start_url", "label": "Start URL", "input_type": "url", "required": True, "placeholder": "https://example.gov.cn/notice"},
                {"name": "max_depth", "label": "Crawl depth", "input_type": "number", "required": True, "min": 0, "max": 5, "step": 1, "default": 2},
                {"name": "respect_robots", "label": "Respect robots", "input_type": "checkbox", "required": True, "default": True},
                {"name": "rate_limit_per_minute", "label": "Rate limit/min", "input_type": "number", "required": True, "min": 1, "max": 120, "step": 1, "default": 30},
                {"name": "allowed_domains", "label": "Allowed domains", "input_type": "tags", "required": False, "default": []},
            ],
        },
        "validation": {
            "policy_endpoint": "PUT /api/v1/data-sources/{data_source_id}/crawl-policy",
            "discovery_endpoint": "POST /api/v1/data-sources/{data_source_id}/public-web/discover-links",
            "forbidden_access_modes": ["cookie_pool", "private_scrape"],
            "robots_default": True,
            "synthetic_supported": True,
        },
        "workflow_refs": ["discover_public_web_links", "fetch_public_web_page"],
        "warnings": [],
    },
    "official_api": {
        "channel": "official_api",
        "label": "Official API",
        "source_type": "official_api",
        "adapter_source_type": "official_api",
        "version": "2026-05-10.at296",
        "status": "ready",
        "schema_kind": "json_schema",
        "required_fields": ["base_url", "auth_type", "secret_ref", "sample_path", "pagination_strategy", "max_pages"],
        "json_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["base_url", "auth_type", "secret_ref", "sample_path", "pagination_strategy", "max_pages"],
            "properties": {
                "base_url": {
                    "type": "string",
                    "format": "uri",
                    "title": "Base URL",
                    "description": "HTTP(S) or synthetic official API base URL.",
                    "x-accepted-schemes": ["https", "http", "synthetic"],
                },
                "auth_type": {
                    "type": "string",
                    "enum": ["api_key", "oauth", "basic", "bearer"],
                    "default": "api_key",
                    "description": "Authentication scheme. Secret material must be referenced by secret_ref only.",
                },
                "secret_ref": {
                    "type": "string",
                    "minLength": 6,
                    "maxLength": 500,
                    "description": "Vault/KMS/secret-manager reference. Plain secret values are not accepted by the product contract.",
                    "x-secret-handling": "reference_only",
                    "x-plaintext-secret-allowed": False,
                },
                "header_name": {
                    "type": "string",
                    "maxLength": 120,
                    "default": "X-API-Key",
                    "description": "Header used for api_key or bearer authentication.",
                },
                "token_url": {
                    "type": "string",
                    "format": "uri",
                    "maxLength": 500,
                    "description": "OAuth token URL reference when auth_type is oauth.",
                },
                "sample_path": {
                    "type": "string",
                    "maxLength": 500,
                    "default": "/xian/issues",
                    "description": "Sample path used by the backend test-connection endpoint.",
                },
                "expected_status": {
                    "type": "integer",
                    "minimum": 100,
                    "maximum": 599,
                    "default": 200,
                    "description": "Expected HTTP status for connection tests.",
                },
                "pagination_strategy": {
                    "type": "string",
                    "enum": ["page", "cursor", "next_url"],
                    "default": "page",
                    "description": "Pagination strategy persisted by the pagination endpoint.",
                },
                "page_param": {"type": "string", "maxLength": 120, "default": "page"},
                "page_size_param": {"type": "string", "maxLength": 120, "default": "page_size"},
                "cursor_param": {"type": "string", "maxLength": 120, "default": "cursor"},
                "next_url_path": {"type": "string", "maxLength": 500},
                "max_pages": {"type": "integer", "minimum": 1, "maximum": 100, "default": 3},
                "dry_run": {"type": "boolean", "default": True},
            },
        },
        "ui_schema": {
            "field_order": ["base_url", "auth_type", "secret_ref", "header_name", "sample_path", "pagination_strategy", "max_pages"],
            "fields": [
                {"name": "base_url", "label": "Base URL", "input_type": "url", "required": True, "placeholder": "https://api.example.gov.cn"},
                {"name": "auth_type", "label": "Auth type", "input_type": "select", "required": True, "options": ["api_key", "oauth", "basic", "bearer"], "default": "api_key"},
                {"name": "secret_ref", "label": "Secret ref", "input_type": "text", "required": True, "placeholder": "vault://team/source/api-key", "secret_handling": "reference_only"},
                {"name": "header_name", "label": "Header name", "input_type": "text", "required": False, "default": "X-API-Key"},
                {"name": "sample_path", "label": "Sample path", "input_type": "text", "required": True, "default": "/xian/issues"},
                {"name": "pagination_strategy", "label": "Pagination", "input_type": "select", "required": True, "options": ["page", "cursor", "next_url"], "default": "page"},
                {"name": "max_pages", "label": "Max pages", "input_type": "number", "required": True, "min": 1, "max": 100, "step": 1, "default": 3},
            ],
        },
        "validation": {
            "auth_endpoint": "PUT /api/v1/data-sources/{data_source_id}/auth",
            "connection_test_endpoint": "POST /api/v1/data-sources/{data_source_id}/test-connection",
            "pagination_endpoint": "PUT /api/v1/data-sources/{data_source_id}/pagination",
            "fetch_endpoint": "POST /api/v1/imports/official-api",
            "plain_secret_fields_allowed": False,
            "forbidden_plain_secret_fields": ["api_key", "secret", "token", "password"],
            "synthetic_supported": True,
        },
        "workflow_refs": ["fetch_official_api_page"],
        "warnings": [],
    },
    "document_file": {
        "channel": "document_file",
        "label": "Document file",
        "source_type": "file_upload",
        "adapter_source_type": "file_upload",
        "version": "2026-05-10.at297",
        "status": "ready",
        "schema_kind": "json_schema",
        "required_fields": ["allowed_file_types", "schema_mapping", "max_file_size_mb"],
        "json_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["allowed_file_types", "schema_mapping", "max_file_size_mb"],
            "properties": {
                "allowed_file_types": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["csv", "json", "jsonl", "txt", "pdf", "docx", "xlsx"]},
                    "minItems": 1,
                    "uniqueItems": True,
                    "default": ["csv", "json", "jsonl", "txt", "pdf", "docx", "xlsx"],
                    "description": "Server-side allowlist used by file_upload policy validation and the upload input accept list.",
                },
                "schema_mapping": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["title_field", "content_field", "city_id"],
                    "properties": {
                        "title_field": {"type": "string", "default": "title"},
                        "content_field": {"type": "string", "default": "content"},
                        "occurred_at_field": {"type": "string", "default": "published_at"},
                        "location_field": {"type": "string", "default": "location"},
                        "external_id_field": {"type": "string", "default": "external_id"},
                        "city_id": {"type": "string", "default": "xian"},
                    },
                    "description": "Import mapping persisted as data_sources.policy.schema before upload/file-run processing.",
                },
                "max_file_size_mb": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 50,
                    "description": "Maximum accepted file size per upload for the source policy.",
                },
                "source_uri": {
                    "type": "string",
                    "maxLength": 500,
                    "default": "synthetic://xian/document-file",
                    "description": "Optional source URI persisted on uploaded file objects; synthetic URIs remain clearly labeled.",
                },
                "is_synthetic": {
                    "type": "boolean",
                    "default": True,
                    "description": "Marks uploaded files as synthetic while still using the real upload, scan, file_object, import, raw-record, lineage, and audit path.",
                },
            },
        },
        "ui_schema": {
            "field_order": ["allowed_file_types", "schema_mapping", "max_file_size_mb", "source_uri", "is_synthetic"],
            "fields": [
                {"name": "allowed_file_types", "label": "Allowed types", "input_type": "tags", "required": True, "options": ["csv", "json", "jsonl", "txt", "pdf", "docx", "xlsx"], "default": ["csv", "json", "jsonl", "txt", "pdf", "docx", "xlsx"]},
                {"name": "schema_mapping", "label": "Schema mapping", "input_type": "object", "required": True, "default": {"title_field": "title", "content_field": "content", "city_id": "xian"}},
                {"name": "max_file_size_mb", "label": "Max size MB", "input_type": "number", "required": True, "min": 1, "max": 100, "step": 1, "default": 50},
                {"name": "source_uri", "label": "Source URI", "input_type": "text", "required": False, "default": "synthetic://xian/document-file"},
                {"name": "is_synthetic", "label": "Synthetic", "input_type": "checkbox", "required": False, "default": True},
            ],
        },
        "validation": {
            "create_source_endpoint": "POST /api/v1/data-sources",
            "upload_endpoint": "POST /api/v1/uploads",
            "file_run_endpoint": "POST /api/v1/collection-jobs/{collection_job_id}/file-runs",
            "forbidden_file_types": ["exe", "js", "html", "zip", "bat", "cmd", "ps1", "sh"],
            "signature_scan_required": True,
            "schema_required": True,
            "synthetic_supported": True,
        },
        "workflow_refs": ["import_uploaded_file"],
        "warnings": [],
    },
    "image_file": {
        "channel": "image_file",
        "label": "Image file",
        "source_type": "media",
        "adapter_source_type": "media",
        "version": "2026-05-10.at298",
        "status": "ready",
        "schema_kind": "json_schema",
        "required_fields": ["allowed_formats", "ocr_policy", "vlm_policy", "redaction_policy"],
        "json_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["allowed_formats", "ocr_policy", "vlm_policy", "redaction_policy"],
            "properties": {
                "allowed_formats": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["jpg", "jpeg", "png", "webp", "tiff", "heic"]},
                    "minItems": 1,
                    "uniqueItems": True,
                    "default": ["jpg", "jpeg", "png", "webp"],
                    "description": "Server-side image extension allowlist for media sources and image imports.",
                },
                "ocr_policy": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["enabled", "engine", "languages", "store_text"],
                    "properties": {
                        "enabled": {"type": "boolean", "default": True},
                        "engine": {"type": "string", "enum": ["synthetic_ocr", "tesseract", "external_ocr"], "default": "synthetic_ocr"},
                        "languages": {"type": "array", "items": {"type": "string", "enum": ["zh-CN", "en"]}, "default": ["zh-CN", "en"]},
                        "store_text": {"type": "boolean", "default": True},
                    },
                },
                "vlm_policy": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["enabled", "provider", "evidence_mode"],
                    "properties": {
                        "enabled": {"type": "boolean", "default": True},
                        "provider": {"type": "string", "enum": ["synthetic_deterministic_caption", "external_vlm", "disabled"], "default": "synthetic_deterministic_caption"},
                        "evidence_mode": {"type": "string", "enum": ["candidate_only"], "default": "candidate_only"},
                    },
                    "description": "VLM/caption outputs are persisted as candidate media-processing records and cannot become report facts without evidence review.",
                },
                "redaction_policy": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["enabled", "strategy", "minors_policy"],
                    "properties": {
                        "enabled": {"type": "boolean", "default": True},
                        "strategy": {"type": "string", "enum": ["mask_faces_and_text", "mask_sensitive_text", "blur_faces"], "default": "mask_faces_and_text"},
                        "minors_policy": {"type": "string", "enum": ["always_mask", "review_required"], "default": "always_mask"},
                    },
                },
                "max_file_size_mb": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
                "source_uri": {"type": "string", "maxLength": 500, "default": "synthetic://xian/image-file"},
                "is_synthetic": {"type": "boolean", "default": True},
            },
        },
        "ui_schema": {
            "field_order": ["allowed_formats", "ocr_policy", "vlm_policy", "redaction_policy", "max_file_size_mb", "source_uri", "is_synthetic"],
            "fields": [
                {"name": "allowed_formats", "label": "Allowed formats", "input_type": "tags", "required": True, "options": ["jpg", "jpeg", "png", "webp", "tiff", "heic"], "default": ["jpg", "jpeg", "png", "webp"]},
                {"name": "ocr_policy", "label": "OCR policy", "input_type": "object", "required": True, "default": {"enabled": True, "engine": "synthetic_ocr", "languages": ["zh-CN", "en"], "store_text": True}},
                {"name": "vlm_policy", "label": "VLM policy", "input_type": "object", "required": True, "default": {"enabled": True, "provider": "synthetic_deterministic_caption", "evidence_mode": "candidate_only"}},
                {"name": "redaction_policy", "label": "Redaction policy", "input_type": "object", "required": True, "default": {"enabled": True, "strategy": "mask_faces_and_text", "minors_policy": "always_mask"}},
                {"name": "max_file_size_mb", "label": "Max size MB", "input_type": "number", "required": False, "min": 1, "max": 50, "step": 1, "default": 20},
                {"name": "source_uri", "label": "Source URI", "input_type": "text", "required": False, "default": "synthetic://xian/image-file"},
                {"name": "is_synthetic", "label": "Synthetic", "input_type": "checkbox", "required": False, "default": True},
            ],
        },
        "validation": {
            "create_source_endpoint": "POST /api/v1/data-sources",
            "import_endpoint": "POST /api/v1/imports/media",
            "media_processing_endpoint": "POST /api/v1/media-processing-runs",
            "redaction_endpoint": "POST /api/v1/redaction-runs/sensitive-fields",
            "redaction_required": True,
            "redaction_disabled_warning": {"code": "IMAGE_REDACTION_DISABLED_RISK", "severity": "warning", "message": "Image sources without redaction must be treated as elevated privacy risk."},
            "processors": ["synthetic_ocr", "synthetic_deterministic_caption", "mask_sensitive_text"],
            "synthetic_supported": True,
        },
        "workflow_refs": ["import_media_file", "process_image_media", "redact_image_media"],
        "warnings": [],
    },
    "video_file": {
        "channel": "video_file",
        "label": "Video file",
        "source_type": "media",
        "adapter_source_type": "media",
        "version": "2026-05-10.at299",
        "status": "ready",
        "schema_kind": "json_schema",
        "required_fields": ["allowed_formats", "keyframe_policy", "asr_policy", "ocr_policy", "vlm_policy", "large_video_policy"],
        "json_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["allowed_formats", "keyframe_policy", "asr_policy", "ocr_policy", "vlm_policy", "large_video_policy"],
            "properties": {
                "allowed_formats": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["mp4", "mov", "webm", "mkv"]},
                    "minItems": 1,
                    "uniqueItems": True,
                    "default": ["mp4", "mov", "webm"],
                    "description": "Server-side video extension allowlist for media sources and video imports.",
                },
                "keyframe_policy": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["strategy", "interval_seconds", "max_keyframes"],
                    "properties": {
                        "strategy": {"type": "string", "enum": ["interval_seconds", "scene_change"], "default": "interval_seconds"},
                        "interval_seconds": {"type": "integer", "minimum": 1, "maximum": 300, "default": 10},
                        "scene_threshold": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.35},
                        "max_keyframes": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 120},
                    },
                    "description": "Keyframes are persisted as processing metadata and remain candidate evidence until review.",
                },
                "asr_policy": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["enabled", "engine", "languages", "store_text"],
                    "properties": {
                        "enabled": {"type": "boolean", "default": True},
                        "engine": {"type": "string", "enum": ["synthetic_asr", "whisper", "external_asr"], "default": "synthetic_asr"},
                        "languages": {"type": "array", "items": {"type": "string", "enum": ["zh-CN", "en"]}, "default": ["zh-CN", "en"]},
                        "store_text": {"type": "boolean", "default": True},
                    },
                },
                "ocr_policy": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["enabled", "engine", "languages", "store_text", "keyframe_only"],
                    "properties": {
                        "enabled": {"type": "boolean", "default": True},
                        "engine": {"type": "string", "enum": ["synthetic_ocr", "tesseract", "external_ocr"], "default": "synthetic_ocr"},
                        "languages": {"type": "array", "items": {"type": "string", "enum": ["zh-CN", "en"]}, "default": ["zh-CN", "en"]},
                        "store_text": {"type": "boolean", "default": True},
                        "keyframe_only": {"type": "boolean", "default": True},
                    },
                },
                "vlm_policy": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["enabled", "provider", "evidence_mode"],
                    "properties": {
                        "enabled": {"type": "boolean", "default": True},
                        "provider": {"type": "string", "enum": ["synthetic_deterministic_caption", "external_vlm", "disabled"], "default": "synthetic_deterministic_caption"},
                        "evidence_mode": {"type": "string", "enum": ["candidate_only"], "default": "candidate_only"},
                    },
                    "description": "Video VLM outputs are persisted as candidate media-processing records and cannot become report facts without evidence review.",
                },
                "large_video_policy": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["threshold_mb", "oversize_action", "max_duration_seconds"],
                    "properties": {
                        "threshold_mb": {"type": "integer", "minimum": 50, "maximum": 2048, "default": 512},
                        "oversize_action": {"type": "string", "enum": ["reject", "defer_chunked_processing", "require_manual_review"], "default": "defer_chunked_processing"},
                        "max_duration_seconds": {"type": "integer", "minimum": 1, "maximum": 21600, "default": 7200},
                    },
                    "description": "Required policy for large or long video assets; missing policy must be rejected by backend validation.",
                },
                "redaction_policy": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["enabled", "strategy", "minors_policy"],
                    "properties": {
                        "enabled": {"type": "boolean", "default": True},
                        "strategy": {"type": "string", "enum": ["mask_faces_and_text", "mask_sensitive_text", "blur_faces"], "default": "mask_faces_and_text"},
                        "minors_policy": {"type": "string", "enum": ["always_mask", "review_required"], "default": "always_mask"},
                    },
                },
                "max_file_size_mb": {"type": "integer", "minimum": 1, "maximum": 2048, "default": 512},
                "source_uri": {"type": "string", "maxLength": 500, "default": "synthetic://xian/video-file"},
                "is_synthetic": {"type": "boolean", "default": True},
            },
        },
        "ui_schema": {
            "field_order": ["allowed_formats", "keyframe_policy", "asr_policy", "ocr_policy", "vlm_policy", "large_video_policy", "redaction_policy", "max_file_size_mb", "source_uri", "is_synthetic"],
            "fields": [
                {"name": "allowed_formats", "label": "Allowed formats", "input_type": "tags", "required": True, "options": ["mp4", "mov", "webm", "mkv"], "default": ["mp4", "mov", "webm"]},
                {"name": "keyframe_policy", "label": "Keyframe policy", "input_type": "object", "required": True, "default": {"strategy": "interval_seconds", "interval_seconds": 10, "scene_threshold": 0.35, "max_keyframes": 120}},
                {"name": "asr_policy", "label": "ASR policy", "input_type": "object", "required": True, "default": {"enabled": True, "engine": "synthetic_asr", "languages": ["zh-CN", "en"], "store_text": True}},
                {"name": "ocr_policy", "label": "OCR policy", "input_type": "object", "required": True, "default": {"enabled": True, "engine": "synthetic_ocr", "languages": ["zh-CN", "en"], "store_text": True, "keyframe_only": True}},
                {"name": "vlm_policy", "label": "VLM policy", "input_type": "object", "required": True, "default": {"enabled": True, "provider": "synthetic_deterministic_caption", "evidence_mode": "candidate_only"}},
                {"name": "large_video_policy", "label": "Large video policy", "input_type": "object", "required": True, "default": {"threshold_mb": 512, "oversize_action": "defer_chunked_processing", "max_duration_seconds": 7200}},
                {"name": "redaction_policy", "label": "Redaction policy", "input_type": "object", "required": False, "default": {"enabled": True, "strategy": "mask_faces_and_text", "minors_policy": "always_mask"}},
                {"name": "max_file_size_mb", "label": "Max size MB", "input_type": "number", "required": False, "min": 1, "max": 2048, "step": 1, "default": 512},
                {"name": "source_uri", "label": "Source URI", "input_type": "text", "required": False, "default": "synthetic://xian/video-file"},
                {"name": "is_synthetic", "label": "Synthetic", "input_type": "checkbox", "required": False, "default": True},
            ],
        },
        "validation": {
            "create_source_endpoint": "POST /api/v1/data-sources",
            "import_endpoint": "POST /api/v1/imports/media",
            "media_processing_endpoint": "POST /api/v1/media-processing-runs",
            "redaction_endpoint": "POST /api/v1/redaction-runs/sensitive-fields",
            "large_video_policy_required": True,
            "large_video_policy_missing_code": "VIDEO_LARGE_POLICY_REQUIRED",
            "processors": ["synthetic_keyframe_sampler", "synthetic_asr", "synthetic_ocr", "synthetic_deterministic_caption", "mask_sensitive_text"],
            "synthetic_supported": True,
        },
        "workflow_refs": ["import_media_file", "extract_video_keyframes", "transcribe_video_asr", "process_video_ocr", "process_video_vlm"],
        "warnings": [],
    },
    "livestream": {
        "channel": "livestream",
        "label": "Livestream",
        "source_type": "live_segment",
        "adapter_source_type": "live_segment",
        "version": "2026-05-10.at300",
        "status": "ready",
        "schema_kind": "json_schema",
        "required_fields": ["stream_url", "stream_protocol", "segment_policy", "buffer_policy", "retention_policy"],
        "json_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["stream_url", "stream_protocol", "segment_policy", "buffer_policy", "retention_policy"],
            "properties": {
                "stream_url": {
                    "type": "string",
                    "format": "uri",
                    "default": "synthetic://xian/livestream/social-issues",
                    "description": "HLS, DASH, RTMP, or synthetic livestream URL.",
                    "x-accepted-schemes": ["https", "http", "rtmp", "synthetic"],
                },
                "stream_protocol": {
                    "type": "string",
                    "enum": ["hls", "dash", "rtmp", "synthetic"],
                    "default": "synthetic",
                    "description": "Livestream protocol used by segment ingestion.",
                },
                "segment_policy": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["segment_seconds", "max_segments_per_run", "dedupe_window_seconds"],
                    "properties": {
                        "segment_seconds": {"type": "integer", "minimum": 2, "maximum": 60, "default": 10},
                        "max_segments_per_run": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 12},
                        "dedupe_window_seconds": {"type": "integer", "minimum": 10, "maximum": 3600, "default": 120},
                    },
                },
                "buffer_policy": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["buffer_seconds", "late_arrival_seconds", "gap_strategy"],
                    "properties": {
                        "buffer_seconds": {"type": "integer", "minimum": 5, "maximum": 600, "default": 60},
                        "late_arrival_seconds": {"type": "integer", "minimum": 0, "maximum": 600, "default": 30},
                        "gap_strategy": {"type": "string", "enum": ["mark_gap", "retry_once", "skip_with_audit"], "default": "mark_gap"},
                    },
                },
                "retention_policy": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["retention_days", "retain_original_segments", "purge_strategy"],
                    "properties": {
                        "retention_days": {"type": "integer", "minimum": 1, "maximum": 30, "default": 7},
                        "retain_original_segments": {"type": "boolean", "default": False},
                        "purge_strategy": {"type": "string", "enum": ["delete_raw_keep_metadata", "delete_all_after_review"], "default": "delete_raw_keep_metadata"},
                    },
                    "description": "Required policy for raw livestream segment retention; missing policy is rejected.",
                },
                "redaction_policy": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["enabled", "strategy"],
                    "properties": {
                        "enabled": {"type": "boolean", "default": True},
                        "strategy": {"type": "string", "enum": ["mask_faces_and_text", "mask_sensitive_text", "blur_faces"], "default": "mask_faces_and_text"},
                    },
                },
                "is_synthetic": {"type": "boolean", "default": True},
            },
        },
        "ui_schema": {
            "field_order": ["stream_url", "stream_protocol", "segment_policy", "buffer_policy", "retention_policy", "redaction_policy", "is_synthetic"],
            "fields": [
                {"name": "stream_url", "label": "Stream URL", "input_type": "url", "required": True, "default": "synthetic://xian/livestream/social-issues"},
                {"name": "stream_protocol", "label": "Protocol", "input_type": "select", "required": True, "options": ["hls", "dash", "rtmp", "synthetic"], "default": "synthetic"},
                {"name": "segment_policy", "label": "Segment policy", "input_type": "object", "required": True, "default": {"segment_seconds": 10, "max_segments_per_run": 12, "dedupe_window_seconds": 120}},
                {"name": "buffer_policy", "label": "Buffer policy", "input_type": "object", "required": True, "default": {"buffer_seconds": 60, "late_arrival_seconds": 30, "gap_strategy": "mark_gap"}},
                {"name": "retention_policy", "label": "Retention policy", "input_type": "object", "required": True, "default": {"retention_days": 7, "retain_original_segments": False, "purge_strategy": "delete_raw_keep_metadata"}},
                {"name": "redaction_policy", "label": "Redaction policy", "input_type": "object", "required": False, "default": {"enabled": True, "strategy": "mask_faces_and_text"}},
                {"name": "is_synthetic", "label": "Synthetic", "input_type": "checkbox", "required": False, "default": True},
            ],
        },
        "validation": {
            "create_source_endpoint": "POST /api/v1/data-sources",
            "import_endpoint": "POST /api/v1/imports/media",
            "media_processing_endpoint": "POST /api/v1/live-segment-runs",
            "retention_policy_required": True,
            "retention_policy_missing_code": "LIVE_RETENTION_POLICY_REQUIRED",
            "supported_protocols": ["hls", "dash", "rtmp", "synthetic"],
            "processors": ["synthetic_livestream_segmenter", "mask_sensitive_text"],
            "synthetic_supported": True,
        },
        "workflow_refs": ["ingest_livestream_segments", "buffer_livestream_window", "process_live_segment"],
        "warnings": [],
    },
    "audio_file": {
        "channel": "audio_file",
        "label": "Audio file",
        "source_type": "media",
        "adapter_source_type": "media",
        "version": "2026-05-10.at301",
        "status": "ready",
        "schema_kind": "json_schema",
        "required_fields": ["allowed_formats", "asr_policy", "segmentation_policy", "language_policy"],
        "json_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["allowed_formats", "asr_policy", "segmentation_policy", "language_policy"],
            "properties": {
                "allowed_formats": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["mp3", "wav", "m4a", "aac", "flac"]},
                    "minItems": 1,
                    "uniqueItems": True,
                    "default": ["mp3", "wav", "m4a"],
                    "description": "Server-side audio extension allowlist for media sources and audio imports.",
                },
                "asr_policy": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["enabled", "engine", "store_text"],
                    "properties": {
                        "enabled": {"type": "boolean", "default": True},
                        "engine": {"type": "string", "enum": ["synthetic_asr", "whisper", "external_asr"], "default": "synthetic_asr"},
                        "store_text": {"type": "boolean", "default": True},
                    },
                },
                "segmentation_policy": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["mode", "segment_seconds", "overlap_seconds"],
                    "properties": {
                        "mode": {"type": "string", "enum": ["fixed_window", "voice_activity"], "default": "fixed_window"},
                        "segment_seconds": {"type": "integer", "minimum": 5, "maximum": 600, "default": 30},
                        "overlap_seconds": {"type": "integer", "minimum": 0, "maximum": 30, "default": 2},
                    },
                },
                "language_policy": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["primary_language", "allowed_languages", "fallback_language"],
                    "properties": {
                        "primary_language": {"type": "string", "enum": ["zh-CN", "en"], "default": "zh-CN"},
                        "allowed_languages": {"type": "array", "items": {"type": "string", "enum": ["zh-CN", "en"]}, "default": ["zh-CN", "en"]},
                        "fallback_language": {"type": "string", "enum": ["zh-CN", "en"], "default": "zh-CN"},
                    },
                    "description": "Unsupported languages are rejected by backend policy validation before import.",
                },
                "redaction_policy": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["enabled", "strategy"],
                    "properties": {
                        "enabled": {"type": "boolean", "default": True},
                        "strategy": {"type": "string", "enum": ["mask_sensitive_text"], "default": "mask_sensitive_text"},
                    },
                },
                "max_file_size_mb": {"type": "integer", "minimum": 1, "maximum": 512, "default": 100},
                "source_uri": {"type": "string", "maxLength": 500, "default": "synthetic://xian/audio-file"},
                "is_synthetic": {"type": "boolean", "default": True},
            },
        },
        "ui_schema": {
            "field_order": ["allowed_formats", "asr_policy", "segmentation_policy", "language_policy", "redaction_policy", "max_file_size_mb", "source_uri", "is_synthetic"],
            "fields": [
                {"name": "allowed_formats", "label": "Allowed formats", "input_type": "tags", "required": True, "options": ["mp3", "wav", "m4a", "aac", "flac"], "default": ["mp3", "wav", "m4a"]},
                {"name": "asr_policy", "label": "ASR policy", "input_type": "object", "required": True, "default": {"enabled": True, "engine": "synthetic_asr", "store_text": True}},
                {"name": "segmentation_policy", "label": "Segmentation policy", "input_type": "object", "required": True, "default": {"mode": "fixed_window", "segment_seconds": 30, "overlap_seconds": 2}},
                {"name": "language_policy", "label": "Language policy", "input_type": "object", "required": True, "default": {"primary_language": "zh-CN", "allowed_languages": ["zh-CN", "en"], "fallback_language": "zh-CN"}},
                {"name": "redaction_policy", "label": "Redaction policy", "input_type": "object", "required": False, "default": {"enabled": True, "strategy": "mask_sensitive_text"}},
                {"name": "max_file_size_mb", "label": "Max size MB", "input_type": "number", "required": False, "min": 1, "max": 512, "step": 1, "default": 100},
                {"name": "source_uri", "label": "Source URI", "input_type": "text", "required": False, "default": "synthetic://xian/audio-file"},
                {"name": "is_synthetic", "label": "Synthetic", "input_type": "checkbox", "required": False, "default": True},
            ],
        },
        "validation": {
            "create_source_endpoint": "POST /api/v1/data-sources",
            "import_endpoint": "POST /api/v1/imports/media",
            "media_processing_endpoint": "POST /api/v1/media-processing-runs",
            "unsupported_language_code": "AUDIO_LANGUAGE_UNSUPPORTED",
            "supported_languages": ["zh-CN", "en"],
            "processors": ["synthetic_asr", "synthetic_audio_segmenter", "mask_sensitive_text"],
            "synthetic_supported": True,
        },
        "workflow_refs": ["import_media_file", "segment_audio_file", "transcribe_audio_asr"],
        "warnings": [],
    },
}


AdapterHandler = Callable[..., dict]


@dataclass(frozen=True)
class AdapterDefinition:
    source_type: str
    label: str
    capabilities: dict
    handlers: dict[str, AdapterHandler]
    status: str = "registered"


def adapter_method_status(adapter: AdapterDefinition) -> dict[str, bool]:
    return {method: callable(adapter.handlers.get(method)) for method in REQUIRED_ADAPTER_METHODS}


def adapter_missing_methods(adapter: AdapterDefinition) -> list[str]:
    status = adapter_method_status(adapter)
    return [method for method, present in status.items() if not present]


def validate_adapter_contract(adapter: AdapterDefinition) -> dict:
    missing = adapter_missing_methods(adapter)
    return {
        "source_type": adapter.source_type,
        "label": adapter.label,
        "status": "failed" if missing else "passed",
        "required_methods": list(REQUIRED_ADAPTER_METHODS),
        "method_status": adapter_method_status(adapter),
        "missing_methods": missing,
        "capabilities": adapter.capabilities,
        "synthetic_supported": bool(adapter.capabilities.get("supports_synthetic", True)) if adapter.capabilities else False,
    }


class AdapterRegistry:
    def __init__(self, adapters: list[AdapterDefinition]):
        self._adapters: dict[str, AdapterDefinition] = {}
        for adapter in adapters:
            self._validate_adapter(adapter)
            if adapter.source_type in self._adapters:
                raise ValueError(f"duplicate adapter registration: {adapter.source_type}")
            self._adapters[adapter.source_type] = adapter

    def _validate_adapter(self, adapter: AdapterDefinition) -> None:
        missing = adapter_missing_methods(adapter)
        if missing:
            raise ValueError(f"adapter {adapter.source_type} missing required methods: {', '.join(missing)}")
        if not adapter.capabilities:
            raise ValueError(f"adapter {adapter.source_type} must declare capabilities")

    def __getitem__(self, source_type: str) -> AdapterDefinition:
        if source_type not in self._adapters:
            raise KeyError(source_type)
        return self._adapters[source_type]

    def get(self, source_type: str) -> AdapterDefinition | None:
        return self._adapters.get(source_type)

    def __iter__(self):
        return iter(self._adapters)

    def __len__(self) -> int:
        return len(self._adapters)

    def values(self):
        return self._adapters.values()

    def to_list(self) -> list[dict]:
        return [serialize_adapter(adapter) for adapter in self._adapters.values()]


def _validate_config(**_kwargs) -> dict:
    return {"status": "ok"}


def _discover(**_kwargs) -> dict:
    return {"status": "registered", "items": []}


def _fetch(**_kwargs) -> dict:
    return {"status": "registered", "records": []}


def _parse(**_kwargs) -> dict:
    return {"status": "registered", "items": []}


def _normalize(**_kwargs) -> dict:
    return {"status": "registered", "items": []}


def _handlers() -> dict[str, AdapterHandler]:
    return {
        "validate_config": _validate_config,
        "discover": _discover,
        "fetch": _fetch,
        "parse": _parse,
        "normalize": _normalize,
    }


def _adapter(source_type: str, label: str, capabilities: dict) -> AdapterDefinition:
    return AdapterDefinition(source_type=source_type, label=label, capabilities=capabilities, handlers=_handlers())


def build_adapter_registry() -> AdapterRegistry:
    return AdapterRegistry(
        [
            _adapter("public_web", "Public web page crawler", {"input": ["start_url", "crawl_policy"], "outputs": ["raw_record", "lineage"], "supports_synthetic": True}),
            _adapter("official_api", "Official API client", {"input": ["base_url", "auth", "pagination"], "outputs": ["raw_record", "lineage"], "supports_synthetic": True}),
            _adapter("rss", "RSS feed reader", {"input": ["feed_url"], "outputs": ["raw_record", "lineage"], "supports_synthetic": True}),
            _adapter("file_upload", "File upload parser", {"input": ["file_object_id", "schema"], "outputs": ["raw_record", "file_object", "lineage"], "supports_synthetic": True}),
            _adapter("media", "Image/video/audio media processor", {"input": ["media_uri", "media_type", "ocr_policy", "vlm_policy", "redaction_policy", "keyframe_policy", "asr_policy", "large_video_policy", "segmentation_policy", "language_policy"], "outputs": ["raw_record", "media_asset", "media_processing_run", "lineage"], "supports_synthetic": True}),
            _adapter("live_segment", "Livestream segment processor", {"input": ["stream_url", "stream_protocol", "segment_policy", "buffer_policy", "retention_policy"], "outputs": ["raw_record", "media_asset", "media_processing_run", "lineage"], "supports_synthetic": True}),
            _adapter("manual", "Manual record entry", {"input": ["entry_schema"], "outputs": ["raw_record", "lineage"], "supports_synthetic": True}),
            _adapter("db_import", "Database import scanner", {"input": ["connection_ref", "secret_ref", "cursor"], "outputs": ["raw_record", "lineage"], "supports_synthetic": True}),
            _adapter("object_storage", "Object storage scanner", {"input": ["bucket", "prefix", "secret_ref"], "outputs": ["raw_record", "file_object", "lineage"], "supports_synthetic": True}),
        ]
    )


ADAPTER_REGISTRY = build_adapter_registry()


def _channel_error(
    error_code: str,
    label: str,
    classification: str,
    severity: str,
    retryable: bool,
    remediation: str,
    run_detail_hint: str,
) -> dict:
    return {
        "error_code": error_code,
        "label": label,
        "classification": classification,
        "severity": severity,
        "retryable": retryable,
        "remediation": remediation,
        "run_detail_hint": run_detail_hint,
    }


COMMON_CHANNEL_ERROR_MAPPINGS = {
    "SOURCE_POLICY_BLOCKED": _channel_error("SOURCE_POLICY_BLOCKED", "Source policy blocked", "policy", "error", False, "Review source authorization, robots/compliance policy, and activation state before retrying.", "Collection was stopped by persisted source policy."),
    "DATA_SOURCE_POLICY_BLOCKED": _channel_error("DATA_SOURCE_POLICY_BLOCKED", "Data source policy blocked", "policy", "error", False, "Update the data source compliance/policy record and rerun policy check.", "Import was blocked by data source policy."),
    "source_inactive": _channel_error("source_inactive", "Source inactive", "state", "warning", False, "Activate the source only after recording the reason and expected health state.", "Source policy marks the source inactive."),
    "source_not_allowed_for_p0": _channel_error("source_not_allowed_for_p0", "Source access mode not allowed", "policy", "error", False, "Use an allowed public, official, authorized export, manual, or synthetic access mode.", "Source access mode is outside the approved P0 boundary."),
    "DATA_SOURCE_DISABLED": _channel_error("DATA_SOURCE_DISABLED", "Data source disabled", "state", "warning", False, "Enable the data source only after recording a reason and health expectation.", "Source is disabled; new runs are not allowed."),
    "SOURCE_RATE_LIMITED": _channel_error("SOURCE_RATE_LIMITED", "Source rate limited", "rate_limit", "warning", True, "Wait for the persisted rate-limit window or lower schedule frequency.", "Run was delayed by the backend rate-limit ledger."),
    "CHANNEL_RATE_LIMITED": _channel_error("CHANNEL_RATE_LIMITED", "Channel rate limited", "rate_limit", "warning", True, "Wait for the persisted channel window or lower only that channel schedule frequency.", "Run was delayed by the backend channel-specific rate-limit ledger."),
    "IMPORT_CONTENT_MISSING": _channel_error("IMPORT_CONTENT_MISSING", "Import content missing", "validation", "warning", False, "Provide request content or mark the request as synthetic so the real ingest path can proceed.", "Import request did not contain processable content."),
}

CHANNEL_ERROR_CODE_MAPPINGS = {
    "web_page": {
        **COMMON_CHANNEL_ERROR_MAPPINGS,
        "PUBLIC_WEB_SOURCE_URI_REQUIRED": _channel_error("PUBLIC_WEB_SOURCE_URI_REQUIRED", "Public web source URI required", "validation", "warning", False, "Set source_uri or persist a crawl policy start_url.", "Web fetch has no start URL."),
        "PUBLIC_WEB_SOURCE_URI_INVALID": _channel_error("PUBLIC_WEB_SOURCE_URI_INVALID", "Public web source URI invalid", "validation", "warning", False, "Use http(s) or labeled synthetic:// URLs only.", "Web fetch URL scheme is unsupported."),
        "PUBLIC_WEB_TIMEOUT": _channel_error("PUBLIC_WEB_TIMEOUT", "Public web timeout", "timeout", "warning", True, "Retry with backoff or lower crawl concurrency.", "Web fetch timed out."),
        "PUBLIC_WEB_FORBIDDEN": _channel_error("PUBLIC_WEB_FORBIDDEN", "Public web forbidden", "forbidden", "error", False, "Do not bypass access controls; use an authorized source or mark the source unavailable.", "Web source returned 403."),
        "PUBLIC_WEB_NON_HTML": _channel_error("PUBLIC_WEB_NON_HTML", "Public web non-HTML response", "validation", "warning", False, "Route JSON/XML/binary content to the matching channel instead of web_page.", "Web fetch returned a non-HTML payload."),
        "PUBLIC_WEB_HTTP_ERROR": _channel_error("PUBLIC_WEB_HTTP_ERROR", "Public web HTTP error", "upstream", "warning", True, "Inspect upstream status and retry only if allowed by policy.", "Web source returned an HTTP error."),
        "PUBLIC_WEB_UNREACHABLE": _channel_error("PUBLIC_WEB_UNREACHABLE", "Public web unreachable", "unreachable", "warning", True, "Retry with backoff and keep the health ledger degraded until successful.", "Web source could not be reached."),
        "PUBLIC_WEB_START_URL_REQUIRED": _channel_error("PUBLIC_WEB_START_URL_REQUIRED", "Public web start URL required", "validation", "warning", False, "Provide a crawl policy start_url before link discovery.", "Link discovery has no start URL."),
    },
    "official_api": {
        **COMMON_CHANNEL_ERROR_MAPPINGS,
        "official_api_key_missing": _channel_error("official_api_key_missing", "Official API key reference missing", "auth", "error", False, "Persist a secret_ref or auth.secret_ref before running official API collection.", "Official API source has no credential reference."),
        "OFFICIAL_API_UNAUTHORIZED": _channel_error("OFFICIAL_API_UNAUTHORIZED", "Official API unauthorized", "auth", "error", False, "Rotate or repair secret_ref credentials; never store plaintext secrets.", "Official API returned 401."),
        "OFFICIAL_API_RATE_LIMITED": _channel_error("OFFICIAL_API_RATE_LIMITED", "Official API rate limited", "rate_limit", "warning", True, "Use retry backoff and lower page or schedule rate.", "Official API returned 429."),
        "OFFICIAL_API_UPSTREAM_ERROR": _channel_error("OFFICIAL_API_UPSTREAM_ERROR", "Official API upstream error", "upstream", "warning", True, "Retry with backoff and keep upstream status visible.", "Official API returned a 5xx response."),
        "OFFICIAL_API_HTTP_ERROR": _channel_error("OFFICIAL_API_HTTP_ERROR", "Official API HTTP error", "upstream", "warning", False, "Inspect endpoint path and request parameters before retrying.", "Official API returned a non-retryable HTTP response."),
        "OFFICIAL_API_TIMEOUT": _channel_error("OFFICIAL_API_TIMEOUT", "Official API timeout", "timeout", "warning", True, "Retry with configured backoff and record provider latency.", "Official API request timed out."),
        "OFFICIAL_API_UNREACHABLE": _channel_error("OFFICIAL_API_UNREACHABLE", "Official API unreachable", "unreachable", "warning", True, "Retry after health recovery or mark source degraded.", "Official API endpoint could not be reached."),
        "OFFICIAL_API_SOURCE_URI_REQUIRED": _channel_error("OFFICIAL_API_SOURCE_URI_REQUIRED", "Official API source URI required", "validation", "warning", False, "Provide source_uri or persist a base_url/sample_path policy.", "Official API fetch has no URI."),
        "OFFICIAL_API_HTTPS_REQUIRED": _channel_error("OFFICIAL_API_HTTPS_REQUIRED", "Official API HTTPS required", "security", "error", False, "Use https or a labeled synthetic:// endpoint.", "Official API endpoint violated HTTPS policy."),
    },
    "rss": {
        **COMMON_CHANNEL_ERROR_MAPPINGS,
        "RSS_FEED_URL_MISSING": _channel_error("RSS_FEED_URL_MISSING", "RSS feed URL missing", "validation", "warning", False, "Persist feed_url or pass source_uri for the RSS run.", "RSS run has no feed URL."),
        "RSS_FEED_INVALID": _channel_error("RSS_FEED_INVALID", "RSS feed invalid", "validation", "warning", False, "Verify the source is RSS/Atom XML and not a generic page.", "RSS payload could not be parsed as a feed."),
        "RSS_FEED_TIMEOUT": _channel_error("RSS_FEED_TIMEOUT", "RSS feed timeout", "timeout", "warning", True, "Retry with backoff and keep source health degraded until success.", "RSS request timed out."),
        "RSS_FEED_UNREACHABLE": _channel_error("RSS_FEED_UNREACHABLE", "RSS feed unreachable", "unreachable", "warning", True, "Retry after source health recovers.", "RSS feed could not be reached."),
        "RSS_FEED_RATE_LIMITED": _channel_error("RSS_FEED_RATE_LIMITED", "RSS feed rate limited", "rate_limit", "warning", True, "Back off schedule and preserve the retry ledger.", "RSS source returned 429."),
        "RSS_FEED_UPSTREAM_ERROR": _channel_error("RSS_FEED_UPSTREAM_ERROR", "RSS feed upstream error", "upstream", "warning", True, "Retry with backoff and surface upstream status.", "RSS source returned a 5xx response."),
        "RSS_FEED_EMPTY": _channel_error("RSS_FEED_EMPTY", "RSS feed empty", "empty", "info", False, "Keep the source active but show empty-state run detail.", "RSS feed returned no items."),
    },
    "document_file": {
        **COMMON_CHANNEL_ERROR_MAPPINGS,
        "FILE_UPLOAD_TYPES_REQUIRED": _channel_error("FILE_UPLOAD_TYPES_REQUIRED", "File upload types required", "validation", "warning", False, "Configure allowed_file_types from the document_file schema.", "Document source lacks allowed file types."),
        "FILE_UPLOAD_TYPE_NOT_ALLOWED": _channel_error("FILE_UPLOAD_TYPE_NOT_ALLOWED", "File upload type not allowed", "validation", "warning", False, "Use one of the backend schema allowed file types.", "Uploaded file extension is blocked."),
        "FILE_UPLOAD_SCHEMA_REQUIRED": _channel_error("FILE_UPLOAD_SCHEMA_REQUIRED", "File upload schema required", "validation", "warning", False, "Persist schema mapping before upload/file-run processing.", "Document source has no import schema."),
        "FILE_UPLOAD_SIZE_LIMIT_INVALID": _channel_error("FILE_UPLOAD_SIZE_LIMIT_INVALID", "File upload size limit invalid", "validation", "warning", False, "Set max_file_size_mb between backend schema bounds.", "Document size limit policy is invalid."),
        "FILE_UPLOAD_TOO_LARGE": _channel_error("FILE_UPLOAD_TOO_LARGE", "File upload too large", "validation", "warning", False, "Reject or route the file through an approved large-file path.", "Uploaded file exceeds source policy."),
        "FILE_UPLOAD_VIRUS_DETECTED": _channel_error("FILE_UPLOAD_VIRUS_DETECTED", "File upload virus signature detected", "security", "critical", False, "Quarantine the file object and do not process downstream records.", "Upload signature scan blocked the file."),
        "FILE_UPLOAD_STORAGE_FAILED": _channel_error("FILE_UPLOAD_STORAGE_FAILED", "File upload storage failed", "storage", "error", True, "Retry only after object-store health is available.", "Backend could not persist the uploaded object."),
        "FILE_OBJECT_STORAGE_MISSING": _channel_error("FILE_OBJECT_STORAGE_MISSING", "File object storage missing", "storage", "error", True, "Verify object-store persistence before replaying the run.", "File object bytes are missing."),
    },
    "image_file": {
        **COMMON_CHANNEL_ERROR_MAPPINGS,
        "MEDIA_FORMATS_REQUIRED": _channel_error("MEDIA_FORMATS_REQUIRED", "Media formats required", "validation", "warning", False, "Configure allowed_formats from the image_file schema.", "Image source lacks allowed formats."),
        "MEDIA_FORMAT_NOT_ALLOWED": _channel_error("MEDIA_FORMAT_NOT_ALLOWED", "Media format not allowed", "validation", "warning", False, "Use a backend schema allowed image format.", "Image media format is blocked."),
        "IMAGE_REDACTION_DISABLED_RISK": _channel_error("IMAGE_REDACTION_DISABLED_RISK", "Image redaction disabled risk", "privacy", "warning", False, "Enable redaction before processing sensitive image evidence.", "Image source is elevated privacy risk."),
    },
    "video_file": {
        **COMMON_CHANNEL_ERROR_MAPPINGS,
        "VIDEO_FORMATS_REQUIRED": _channel_error("VIDEO_FORMATS_REQUIRED", "Video formats required", "validation", "warning", False, "Configure allowed_formats from the video_file schema.", "Video source lacks allowed formats."),
        "VIDEO_FORMAT_NOT_ALLOWED": _channel_error("VIDEO_FORMAT_NOT_ALLOWED", "Video format not allowed", "validation", "warning", False, "Use a backend schema allowed video format.", "Video media format is blocked."),
        "VIDEO_KEYFRAME_STRATEGY_UNSUPPORTED": _channel_error("VIDEO_KEYFRAME_STRATEGY_UNSUPPORTED", "Video keyframe strategy unsupported", "validation", "warning", False, "Use interval_seconds or scene_change keyframe strategy.", "Video keyframe policy is unsupported."),
        "VIDEO_ASR_ENGINE_UNSUPPORTED": _channel_error("VIDEO_ASR_ENGINE_UNSUPPORTED", "Video ASR engine unsupported", "validation", "warning", False, "Use the backend-declared ASR engine.", "Video ASR policy is unsupported."),
        "VIDEO_OCR_ENGINE_UNSUPPORTED": _channel_error("VIDEO_OCR_ENGINE_UNSUPPORTED", "Video OCR engine unsupported", "validation", "warning", False, "Use the backend-declared OCR engine.", "Video OCR policy is unsupported."),
        "VIDEO_VLM_PROVIDER_UNSUPPORTED": _channel_error("VIDEO_VLM_PROVIDER_UNSUPPORTED", "Video VLM provider unsupported", "validation", "warning", False, "Use the backend-declared VLM provider.", "Video VLM policy is unsupported."),
        "VIDEO_VLM_EVIDENCE_MODE_UNSUPPORTED": _channel_error("VIDEO_VLM_EVIDENCE_MODE_UNSUPPORTED", "Video VLM evidence mode unsupported", "validation", "error", False, "Keep VLM output candidate_only until evidence review promotes it.", "Video VLM output attempted to bypass candidate-only mode."),
        "VIDEO_LARGE_POLICY_REQUIRED": _channel_error("VIDEO_LARGE_POLICY_REQUIRED", "Video large-file policy required", "validation", "warning", False, "Persist large_video_policy before processing large or long videos.", "Video source has no large-video policy."),
        "VIDEO_LARGE_ACTION_UNSUPPORTED": _channel_error("VIDEO_LARGE_ACTION_UNSUPPORTED", "Video large-file action unsupported", "validation", "warning", False, "Use reject, segment, or async_review oversize action.", "Large-video policy action is unsupported."),
        "VIDEO_REDACTION_DISABLED_RISK": _channel_error("VIDEO_REDACTION_DISABLED_RISK", "Video redaction disabled risk", "privacy", "warning", False, "Enable redaction or record elevated privacy risk before processing.", "Video source is elevated privacy risk."),
    },
    "livestream": {
        **COMMON_CHANNEL_ERROR_MAPPINGS,
        "LIVE_STREAM_URL_REQUIRED": _channel_error("LIVE_STREAM_URL_REQUIRED", "Livestream URL required", "validation", "warning", False, "Provide stream_url from the livestream schema.", "Livestream source has no stream URL."),
        "LIVE_STREAM_URL_SCHEME_UNSUPPORTED": _channel_error("LIVE_STREAM_URL_SCHEME_UNSUPPORTED", "Livestream URL scheme unsupported", "validation", "warning", False, "Use https, http, rtmp, or labeled synthetic:// stream URLs.", "Livestream URL scheme is unsupported."),
        "LIVE_STREAM_PROTOCOL_UNSUPPORTED": _channel_error("LIVE_STREAM_PROTOCOL_UNSUPPORTED", "Livestream protocol unsupported", "validation", "warning", False, "Use hls, dash, rtmp, or synthetic protocol.", "Livestream protocol is unsupported."),
        "LIVE_STREAM_PROTOCOL_URL_MISMATCH": _channel_error("LIVE_STREAM_PROTOCOL_URL_MISMATCH", "Livestream protocol URL mismatch", "validation", "warning", False, "Align protocol with URL scheme before ingest.", "Livestream protocol does not match URL scheme."),
        "LIVE_SEGMENT_SECONDS_INVALID": _channel_error("LIVE_SEGMENT_SECONDS_INVALID", "Livestream segment length invalid", "validation", "warning", False, "Set segment_seconds within backend schema bounds.", "Livestream segment policy is invalid."),
        "LIVE_BUFFER_SECONDS_INVALID": _channel_error("LIVE_BUFFER_SECONDS_INVALID", "Livestream buffer invalid", "validation", "warning", False, "Set buffer_seconds within backend schema bounds.", "Livestream buffer policy is invalid."),
        "LIVE_RETENTION_POLICY_REQUIRED": _channel_error("LIVE_RETENTION_POLICY_REQUIRED", "Livestream retention policy required", "validation", "warning", False, "Persist retention_policy before ingesting live segments.", "Livestream source has no retention policy."),
        "LIVE_RETENTION_DAYS_INVALID": _channel_error("LIVE_RETENTION_DAYS_INVALID", "Livestream retention days invalid", "validation", "warning", False, "Set retention_days within backend schema bounds.", "Livestream retention policy is invalid."),
        "LIVE_REDACTION_STRATEGY_UNSUPPORTED": _channel_error("LIVE_REDACTION_STRATEGY_UNSUPPORTED", "Livestream redaction strategy unsupported", "validation", "warning", False, "Use the backend-declared redaction strategy.", "Livestream redaction policy is unsupported."),
    },
    "audio_file": {
        **COMMON_CHANNEL_ERROR_MAPPINGS,
        "AUDIO_FORMATS_REQUIRED": _channel_error("AUDIO_FORMATS_REQUIRED", "Audio formats required", "validation", "warning", False, "Configure allowed_formats from the audio_file schema.", "Audio source lacks allowed formats."),
        "AUDIO_FORMAT_NOT_ALLOWED": _channel_error("AUDIO_FORMAT_NOT_ALLOWED", "Audio format not allowed", "validation", "warning", False, "Use a backend schema allowed audio format.", "Audio media format is blocked."),
        "AUDIO_ASR_ENGINE_UNSUPPORTED": _channel_error("AUDIO_ASR_ENGINE_UNSUPPORTED", "Audio ASR engine unsupported", "validation", "warning", False, "Use the backend-declared ASR engine.", "Audio ASR policy is unsupported."),
        "AUDIO_SEGMENTATION_MODE_UNSUPPORTED": _channel_error("AUDIO_SEGMENTATION_MODE_UNSUPPORTED", "Audio segmentation mode unsupported", "validation", "warning", False, "Use the backend-declared segmentation mode.", "Audio segmentation policy is unsupported."),
        "AUDIO_SEGMENT_SECONDS_INVALID": _channel_error("AUDIO_SEGMENT_SECONDS_INVALID", "Audio segment length invalid", "validation", "warning", False, "Set segment_seconds within backend schema bounds.", "Audio segment policy is invalid."),
        "AUDIO_OVERLAP_SECONDS_INVALID": _channel_error("AUDIO_OVERLAP_SECONDS_INVALID", "Audio overlap invalid", "validation", "warning", False, "Use overlap_seconds shorter than segment_seconds and within backend bounds.", "Audio overlap policy is invalid."),
        "AUDIO_LANGUAGE_UNSUPPORTED": _channel_error("AUDIO_LANGUAGE_UNSUPPORTED", "Audio language unsupported", "validation", "warning", False, "Use supported language policy values: zh-CN and/or en.", "Audio language policy is unsupported."),
        "AUDIO_REDACTION_STRATEGY_UNSUPPORTED": _channel_error("AUDIO_REDACTION_STRATEGY_UNSUPPORTED", "Audio redaction strategy unsupported", "validation", "warning", False, "Use the backend-declared redaction strategy.", "Audio redaction policy is unsupported."),
    },
    "webhook": {
        **COMMON_CHANNEL_ERROR_MAPPINGS,
        "WEBHOOK_DELIVERY_ID_REQUIRED": _channel_error("WEBHOOK_DELIVERY_ID_REQUIRED", "Webhook delivery id required", "validation", "warning", False, "Send a unique delivery id header for each webhook payload.", "Webhook request has no delivery id."),
        "WEBHOOK_REPLAY_DETECTED": _channel_error("WEBHOOK_REPLAY_DETECTED", "Webhook replay detected", "idempotency", "warning", False, "Do not replay already accepted deliveries unless using the replay ledger.", "Webhook delivery was already processed."),
        "WEBHOOK_REQUEST_ID_DUPLICATE": _channel_error("WEBHOOK_REQUEST_ID_DUPLICATE", "Webhook request id duplicate", "idempotency", "warning", False, "Use a unique request_id for each business payload.", "Webhook request_id was already processed."),
        "WEBHOOK_SECRET_UNAVAILABLE": _channel_error("WEBHOOK_SECRET_UNAVAILABLE", "Webhook secret unavailable", "dependency", "error", True, "Restore local secret manager state before accepting payloads.", "Webhook signing secret is unavailable."),
        "WEBHOOK_SIGNATURE_INVALID": _channel_error("WEBHOOK_SIGNATURE_INVALID", "Webhook signature invalid", "auth", "error", False, "Reject the payload and rotate the webhook secret if needed.", "Webhook signature verification failed."),
        "WEBHOOK_PAYLOAD_INVALID": _channel_error("WEBHOOK_PAYLOAD_INVALID", "Webhook payload invalid", "validation", "warning", False, "Send a JSON object payload matching the source schema.", "Webhook payload is not valid JSON object."),
        "WEBHOOK_SCHEMA_INVALID": _channel_error("WEBHOOK_SCHEMA_INVALID", "Webhook schema invalid", "validation", "warning", False, "Include required title/content/request fields.", "Webhook payload is missing required fields."),
    },
    "database": {
        **COMMON_CHANNEL_ERROR_MAPPINGS,
        "db_import_secret_ref_missing": _channel_error("db_import_secret_ref_missing", "DB import secret ref missing", "auth", "error", False, "Persist secret_ref before running DB import collection.", "DB import source has no credential reference."),
        "DB_IMPORT_PLAINTEXT_SECRET_NOT_ALLOWED": _channel_error("DB_IMPORT_PLAINTEXT_SECRET_NOT_ALLOWED", "DB import plaintext secret blocked", "security", "error", False, "Store credentials only as secret_ref.", "DB import policy attempted to store plaintext secret."),
        "DB_IMPORT_CONNECTION_REF_REQUIRED": _channel_error("DB_IMPORT_CONNECTION_REF_REQUIRED", "DB import connection ref required", "validation", "warning", False, "Persist connection_ref before scan.", "DB import source lacks connection_ref."),
        "DB_IMPORT_SECRET_REF_REQUIRED": _channel_error("DB_IMPORT_SECRET_REF_REQUIRED", "DB import secret ref required", "validation", "warning", False, "Persist secret_ref before scan.", "DB import source lacks secret_ref."),
        "DB_IMPORT_ENGINE_UNSUPPORTED": _channel_error("DB_IMPORT_ENGINE_UNSUPPORTED", "DB import engine unsupported", "validation", "warning", False, "Use a backend-supported database engine.", "DB import engine is unsupported."),
        "DB_IMPORT_PERMISSION_DENIED": _channel_error("DB_IMPORT_PERMISSION_DENIED", "DB import permission denied", "auth", "error", False, "Repair source permissions; do not escalate beyond approved read scope.", "DB import credentials cannot read the requested table."),
        "DB_IMPORT_CONNECTION_FAILED": _channel_error("DB_IMPORT_CONNECTION_FAILED", "DB import connection failed", "dependency", "warning", True, "Retry after connection health recovers.", "DB import connection failed."),
    },
    "object_storage": {
        **COMMON_CHANNEL_ERROR_MAPPINGS,
        "object_storage_secret_ref_missing": _channel_error("object_storage_secret_ref_missing", "Object storage secret ref missing", "auth", "error", False, "Persist secret_ref before running object storage collection.", "Object storage source has no credential reference."),
        "OBJECT_STORAGE_PLAINTEXT_SECRET_NOT_ALLOWED": _channel_error("OBJECT_STORAGE_PLAINTEXT_SECRET_NOT_ALLOWED", "Object storage plaintext secret blocked", "security", "error", False, "Store credentials only as secret_ref.", "Object storage policy attempted to store plaintext secret."),
        "OBJECT_STORAGE_BUCKET_REQUIRED": _channel_error("OBJECT_STORAGE_BUCKET_REQUIRED", "Object storage bucket required", "validation", "warning", False, "Persist bucket before listing or scanning.", "Object storage source lacks bucket."),
        "OBJECT_STORAGE_SECRET_REF_REQUIRED": _channel_error("OBJECT_STORAGE_SECRET_REF_REQUIRED", "Object storage secret ref required", "validation", "warning", False, "Persist secret_ref before listing or scanning.", "Object storage source lacks secret_ref."),
        "OBJECT_STORAGE_PREFIX_INVALID": _channel_error("OBJECT_STORAGE_PREFIX_INVALID", "Object storage prefix invalid", "validation", "warning", False, "Use a string prefix.", "Object storage prefix policy is invalid."),
        "OBJECT_STORAGE_BUCKET_FORBIDDEN": _channel_error("OBJECT_STORAGE_BUCKET_FORBIDDEN", "Object storage bucket forbidden", "auth", "error", False, "Repair bucket permissions within approved scope.", "Object storage permissions deny list or scan."),
        "OBJECT_STORAGE_FILE_MISSING": _channel_error("OBJECT_STORAGE_FILE_MISSING", "Object storage file missing", "dependency", "warning", True, "Retry after object listing stabilizes.", "Listed objects disappeared before fetch."),
    },
}


def _fallback_error_mapping(channel: str, error_code: str) -> dict:
    return {
        "channel": channel,
        "error_code": error_code,
        "known": False,
        "label": "Unmapped channel error",
        "classification": "unknown",
        "severity": "warning",
        "retryable": False,
        "remediation": "Register this error in map_channel_error_codes before freezing the affected channel workflow.",
        "run_detail_hint": f"Unmapped {channel} error {error_code}; inspect persisted run, import, and source health payloads.",
        "source": "map_channel_error_codes",
    }


def map_channel_error_codes(channel: str | None = None, error_code: str | None = None) -> dict:
    channel_filter = channel.strip() if isinstance(channel, str) and channel.strip() else None
    error_filter = error_code.strip() if isinstance(error_code, str) and error_code.strip() else None
    definitions_by_channel = {definition["channel"]: definition for definition in COLLECTION_CHANNEL_DEFINITIONS}
    selected_channels = [channel_filter] if channel_filter else [definition["channel"] for definition in COLLECTION_CHANNEL_DEFINITIONS]
    channels: list[dict] = []
    results: list[dict] = []
    warnings: list[dict] = []
    unknown_count = 0

    for selected_channel in selected_channels:
        definition = definitions_by_channel.get(selected_channel)
        mappings_by_code = CHANNEL_ERROR_CODE_MAPPINGS.get(selected_channel, {})
        fallback = {
            "classification": "unknown",
            "severity": "warning",
            "retryable": False,
            "warning_code": "CHANNEL_ERROR_CODE_UNMAPPED",
        }
        mapping_rows = [{**mapping, "channel": selected_channel, "known": True, "source": "map_channel_error_codes"} for mapping in mappings_by_code.values()]
        channels.append(
            {
                "channel": selected_channel,
                "label": (definition or {}).get("label", selected_channel),
                "source_type": (definition or {}).get("source_type"),
                "adapter_source_type": (definition or {}).get("adapter_source_type"),
                "mapping_count": len(mapping_rows),
                "mappings": sorted(mapping_rows, key=lambda item: item["error_code"]),
                "fallback": fallback,
            }
        )
        if error_filter:
            mapping = mappings_by_code.get(error_filter)
            if mapping is not None:
                results.append({**mapping, "channel": selected_channel, "known": True, "source": "map_channel_error_codes"})
            elif definition is not None or channel_filter:
                unknown = _fallback_error_mapping(selected_channel, error_filter)
                results.append(unknown)
                unknown_count += 1
                warnings.append(
                    {
                        "code": "CHANNEL_ERROR_CODE_UNMAPPED",
                        "severity": "warning",
                        "channel": selected_channel,
                        "error_code": error_filter,
                        "message": f"Error code {error_filter} is not mapped for channel {selected_channel}.",
                    }
                )
        elif not channel_filter:
            results.extend(mapping_rows)
        else:
            results.extend(mapping_rows)

    if channel_filter and channel_filter not in definitions_by_channel:
        warnings.append(
            {
                "code": "CHANNEL_NOT_REGISTERED_FOR_ERROR_MAPPING",
                "severity": "warning",
                "channel": channel_filter,
                "message": f"Channel {channel_filter} is not registered in the collection channel registry.",
            }
        )

    mapping_count = sum(item["mapping_count"] for item in channels)
    return {
        "service": "map_channel_error_codes",
        "version": "2026-05-10.at302",
        "status": "ready" if mapping_count else "degraded",
        "requested": {"channel": channel_filter, "error_code": error_filter},
        "summary": {
            "channel_count": len(COLLECTION_CHANNEL_DEFINITIONS),
            "returned_channel_count": len(channels),
            "mapping_count": len(results) if (channel_filter or error_filter) else mapping_count,
            "registered_mapping_count": mapping_count,
            "unknown_count": unknown_count,
            "warning_count": len(warnings),
        },
        "channels": channels,
        "results": sorted(results, key=lambda item: (item["channel"], item["error_code"])),
        "warnings": warnings,
    }


def serialize_adapter(adapter: AdapterDefinition) -> dict:
    contract = validate_adapter_contract(adapter)
    return {
        "source_type": adapter.source_type,
        "label": adapter.label,
        "status": adapter.status,
        "capabilities": adapter.capabilities,
        "required_methods": list(REQUIRED_ADAPTER_METHODS),
        "method_status": contract["method_status"],
        "missing_methods": contract["missing_methods"],
        "contract_status": contract["status"],
    }


def validate_channel_adapter_contract(
    data_source_types: list[dict] | None = None,
    registry: AdapterRegistry | None = None,
    channel_definitions: list[dict] | None = None,
) -> dict:
    registry = registry or ADAPTER_REGISTRY
    channel_definitions = channel_definitions or COLLECTION_CHANNEL_DEFINITIONS
    source_type_index = {item["source_type"]: item for item in data_source_types or []}
    channel_refs_by_adapter: dict[str, list[str]] = {}
    for definition in channel_definitions:
        channel_refs_by_adapter.setdefault(definition["adapter_source_type"], []).append(definition["channel"])

    adapter_rows: list[dict] = []
    failure_count = 0
    for adapter in registry.values():
        contract = validate_adapter_contract(adapter)
        if contract["missing_methods"]:
            failure_count += 1
        adapter_rows.append(
            {
                **contract,
                "channel_refs": channel_refs_by_adapter.get(adapter.source_type, []),
            }
        )

    channel_rows: list[dict] = []
    degraded_channel_count = 0
    for definition in channel_definitions:
        source_type = definition["source_type"]
        adapter_source_type = definition["adapter_source_type"]
        source_type_meta = source_type_index.get(source_type)
        adapter = registry.get(adapter_source_type)
        warnings: list[dict] = []
        missing_methods: list[str] = []
        method_status: dict[str, bool] = {method: False for method in REQUIRED_ADAPTER_METHODS}
        if source_type_meta is None:
            contract_status = "not_configured"
            degraded_channel_count += 1
            warnings.append({"code": "CHANNEL_SOURCE_TYPE_NOT_CONFIGURED", "message": f"Source type {source_type} is not registered."})
        elif adapter is None:
            contract_status = "degraded"
            degraded_channel_count += 1
            warnings.append({"code": "CHANNEL_ADAPTER_NOT_REGISTERED", "message": f"Adapter {adapter_source_type} is not registered; channel requires a dedicated adapter contract before full automation."})
        else:
            contract = validate_adapter_contract(adapter)
            missing_methods = contract["missing_methods"]
            method_status = contract["method_status"]
            if missing_methods:
                contract_status = "failed"
                failure_count += 1
                warnings.append({"code": "CHANNEL_ADAPTER_CONTRACT_FAILED", "message": f"Adapter {adapter_source_type} is missing methods: {', '.join(missing_methods)}."})
            else:
                contract_status = "passed"
        if adapter is not None:
            contract = validate_adapter_contract(adapter)
            missing_methods = contract["missing_methods"]
            method_status = contract["method_status"]
        channel_rows.append(
            {
                "channel": definition["channel"],
                "source_type": source_type,
                "adapter_source_type": adapter_source_type,
                "adapter_registered": adapter is not None,
                "contract_status": contract_status,
                "required_methods": list(REQUIRED_ADAPTER_METHODS),
                "method_status": method_status,
                "missing_methods": missing_methods,
                "warnings": warnings,
            }
        )

    return {
        "service": "validate_channel_adapter_contract",
        "status": "failed" if failure_count else "passed",
        "required_methods": list(REQUIRED_ADAPTER_METHODS),
        "adapter_count": len(adapter_rows),
        "checked_channel_count": len(channel_rows),
        "failure_count": failure_count,
        "degraded_channel_count": degraded_channel_count,
        "adapters": adapter_rows,
        "channels": channel_rows,
    }


def get_collection_channel_schema(channel: str) -> dict:
    if channel not in COLLECTION_CHANNEL_CONFIG_SCHEMAS:
        raise KeyError(channel)
    schema = COLLECTION_CHANNEL_CONFIG_SCHEMAS[channel]
    adapter = ADAPTER_REGISTRY.get(schema["adapter_source_type"])
    return {
        **schema,
        "adapter_registered": adapter is not None,
        "adapter_contract_status": validate_adapter_contract(adapter)["status"] if adapter is not None else "degraded",
    }


def collection_channel_registry(data_source_types: list[dict]) -> list[dict]:
    source_type_index = {item["source_type"]: item for item in data_source_types}
    rows: list[dict] = []
    for definition in COLLECTION_CHANNEL_DEFINITIONS:
        source_type = definition["source_type"]
        adapter_source_type = definition["adapter_source_type"]
        source_type_meta = source_type_index.get(source_type)
        adapter = ADAPTER_REGISTRY.get(adapter_source_type)
        warnings: list[dict] = []
        if source_type_meta is None:
            status = "not_configured"
            warnings.append({"code": "CHANNEL_SOURCE_TYPE_NOT_CONFIGURED", "message": f"Source type {source_type} is not registered."})
        elif adapter is None:
            status = "degraded"
            warnings.append({"code": "CHANNEL_ADAPTER_NOT_REGISTERED", "message": f"Adapter {adapter_source_type} is not registered; channel requires a dedicated adapter contract before full automation."})
        else:
            status = "available"
        capabilities = adapter.capabilities if adapter is not None else {"input": [], "outputs": [], "supports_synthetic": True}
        rows.append(
            {
                "channel": definition["channel"],
                "label": definition["label"],
                "source_type": source_type,
                "adapter_source_type": adapter_source_type,
                "status": status,
                "configured": source_type_meta is not None,
                "adapter_registered": adapter is not None,
                "requires_external_key": bool((source_type_meta or {}).get("requires_external_key", False)),
                "capabilities": capabilities,
                "synthetic_supported": bool(capabilities.get("supports_synthetic", True)),
                "schema_path": definition["schema_path"],
                "quality_metrics_path": f"/api/v1/collection-channels/{definition['channel']}/quality-metrics",
                "warnings": warnings,
            }
        )
    return rows
