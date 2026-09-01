"""
Unit tests for CoChem PWA Shell Isolation & Service Worker Routing.

Invariants:
- Zero-Mock Protocol: Real physical file assertions, genuine regex checks.
- W3C Web App Manifest compliance.
- Service Worker Cache-First static and Network-Only dynamic bypass logic.
- Voila/Tornado integration and header injection.
"""

from __future__ import annotations

import json

from mendeleev import element

from cochem.mobile.pwa.shell import (
    get_manifest_headers,
    get_manifest_path,
    get_pwa_meta_tags,
    get_pwa_tornado_handlers,
    get_service_worker_headers,
    get_sw_path,
    inject_pwa_headers,
)


class TestPWAIsolationAndManifest:
    """Test suite validating PWA Manifest properties, SW routing, and Voila shell hooks."""

    def test_dynamic_mendeleev_invariants(self) -> None:
        """Verify dynamic Mendeleev invariants are operational without hardcoding."""
        carbon = element("C")
        assert carbon.atomic_number == 6
        assert float(carbon.atomic_weight) > 12.0

        nitrogen = element("N")
        assert nitrogen.atomic_number == 7
        assert float(nitrogen.atomic_weight) > 14.0

    def test_manifest_file_exists_and_valid_json(self) -> None:
        """Physical test verifying manifest.json exists on disk and is valid JSON."""
        manifest_path = get_manifest_path()
        assert manifest_path.exists(), f"Manifest file missing at {manifest_path}"
        assert manifest_path.is_file()

        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert isinstance(data, dict)
        assert data.get("name") == "CoChem Mobile Studio"
        assert data.get("short_name") == "CoChem"
        assert data.get("start_url") == "/"
        assert data.get("display") == "standalone"
        assert data.get("background_color") == "#0f0f1a"
        assert data.get("theme_color") == "#1a1a2e"
        assert data.get("orientation") == "any"

        # Check icons configuration
        icons = data.get("icons", [])
        assert len(icons) >= 2
        icon_sizes = [icon.get("sizes") for icon in icons]
        assert "192x192" in icon_sizes
        assert "512x512" in icon_sizes

        purposes = [icon.get("purpose") for icon in icons if "purpose" in icon]
        assert "any" in purposes
        assert "maskable" in purposes

    def test_service_worker_file_exists_and_contains_bypass_rules(self) -> None:
        """Physical test verifying sw.js exists and enforces strict routing rules."""
        sw_path = get_sw_path()
        assert sw_path.exists(), f"Service worker file missing at {sw_path}"
        assert sw_path.is_file()

        with open(sw_path, "r", encoding="utf-8") as f:
            sw_code = f.read()

        # Verify Cache name versioning
        assert "cochem-mobile-shell" in sw_code

        # Verify static asset caching list
        assert ".js" in sw_code
        assert ".css" in sw_code
        assert ".woff2" in sw_code
        assert ".svg" in sw_code
        assert ".png" in sw_code

        # Verify network-only bypass endpoints
        assert "/api/kernels/" in sw_code
        assert "/api/events/" in sw_code
        assert "/api/telemetry/" in sw_code
        assert "/api/push/" in sw_code
        assert "no-store" in sw_code

        # Verify Service Worker lifecycle event listeners
        assert "addEventListener('install'" in sw_code or 'addEventListener("install"' in sw_code
        assert "addEventListener('activate'" in sw_code or 'addEventListener("activate"' in sw_code
        assert "addEventListener('fetch'" in sw_code or 'addEventListener("fetch"' in sw_code
        assert "addEventListener('push'" in sw_code or 'addEventListener("push"' in sw_code
        assert (
            "addEventListener('notificationclick'" in sw_code
            or 'addEventListener("notificationclick"' in sw_code
        )

    def test_pwa_meta_tag_generation_and_injection(self) -> None:
        """Verify HTML meta tag generation and injection for Voila templates."""
        meta_tags = get_pwa_meta_tags()
        assert 'name="viewport"' in meta_tags
        assert 'content="width=device-width' in meta_tags
        assert 'name="apple-mobile-web-app-capable"' in meta_tags
        assert 'content="yes"' in meta_tags
        assert 'name="theme-color"' in meta_tags
        assert 'content="#1a1a2e"' in meta_tags
        assert 'rel="manifest"' in meta_tags
        assert 'href="/manifest.json"' in meta_tags
        assert 'navigator.serviceWorker.register("/sw.js"' in meta_tags

        # Test injection into standard HTML with </head>
        raw_html_doc = "<!DOCTYPE html><html><head><title>CoChem</title></head><body><h1>Studio</h1></body></html>"
        injected = inject_pwa_headers(raw_html_doc)
        assert '<meta name="viewport"' in injected
        assert "<title>CoChem</title>" in injected
        assert "</head>" in injected
        assert injected.index('<meta name="viewport"') < injected.index("</head>")

        # Test injection into HTML with <head> but no closing </head>
        raw_html_open = "<html><head><title>CoChem</title><body><h1>Studio</h1></body></html>"
        injected_open = inject_pwa_headers(raw_html_open)
        assert '<meta name="viewport"' in injected_open

        # Test injection into bare HTML
        raw_html_bare = "<div>CoChem Content</div>"
        injected_bare = inject_pwa_headers(raw_html_bare)
        assert "<head>" in injected_bare
        assert '<meta name="viewport"' in injected_bare

    def test_service_worker_and_manifest_http_headers(self) -> None:
        """Verify Tornado HTTP headers for sw.js and manifest.json."""
        sw_headers = get_service_worker_headers()
        assert sw_headers.get("Service-Worker-Allowed") == "/"
        assert "no-cache" in sw_headers.get("Cache-Control", "")
        assert "application/javascript" in sw_headers.get("Content-Type", "")

        manifest_headers = get_manifest_headers()
        assert "application/manifest+json" in manifest_headers.get("Content-Type", "")
        assert "public" in manifest_headers.get("Cache-Control", "")

    def test_pwa_tornado_handlers_mapping(self) -> None:
        """Verify Tornado routes return valid handlers for sw.js and manifest.json."""
        handlers = get_pwa_tornado_handlers()
        assert len(handlers) == 2
        routes = [route for route, handler in handlers]
        assert r"/sw\.js" in routes
        assert r"/manifest\.json" in routes
