"""Browser-level visual smoke test for local IncidentPilot interfaces."""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

OUTPUT_DIRECTORY = Path("data/playwright")
PAGES = {
    "dashboard": "http://127.0.0.1:8083/",
    "services": "http://127.0.0.1:8083/services",
    "incidents": "http://127.0.0.1:8083/incidents",
    "reports": "http://127.0.0.1:8083/reports",
    "settings": "http://127.0.0.1:8083/settings",
    "demo-frontend": "http://127.0.0.1:8082/",
    "grafana": "http://127.0.0.1:3001/",
}


def main() -> None:
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for viewport_name, viewport in {
            "desktop": {"width": 1440, "height": 1000},
            "mobile": {"width": 390, "height": 844},
        }.items():
            context = browser.new_context(viewport=viewport)
            page = context.new_page()
            console_errors: list[str] = []
            page.on(
                "console",
                lambda message: (
                    console_errors.append(message.text)
                    if message.type == "error"
                    else None
                ),
            )
            page.on(
                "pageerror",
                lambda error: console_errors.append(str(error)),
            )

            for name, url in PAGES.items():
                response = page.goto(
                    url, wait_until="networkidle", timeout=15_000
                )
                if name == "grafana":
                    page.wait_for_timeout(2_000)
                status = response.status if response else 0
                title = page.title()
                body_text = page.locator("body").inner_text().strip()
                screenshot = OUTPUT_DIRECTORY / (
                    f"{viewport_name}-{name}.png"
                )
                page.screenshot(path=str(screenshot), full_page=True)
                print(
                    f"{viewport_name:7} {name:13} "
                    f"HTTP {status} title={title!r} "
                    f"text={len(body_text)} screenshot={screenshot}"
                )
                if status >= 400 or not body_text:
                    failures.append(
                        f"{viewport_name}/{name}: HTTP {status}, "
                        f"body length {len(body_text)}"
                    )

                if name == "dashboard":
                    busy_state = page.evaluate(
                        """() => {
                          const form = document.querySelector(
                            'form[action="/actions/scenarios/FS-001"]'
                          );
                          form.addEventListener(
                            "submit",
                            (event) => event.preventDefault(),
                            { once: true },
                          );
                          form.requestSubmit();
                          const buttons = Array.from(
                            document.querySelectorAll(
                              '[data-action-scope="scenario"] button'
                            )
                          );
                          return {
                            allDisabled: buttons.every(
                              (button) => button.disabled
                            ),
                            busy: form.getAttribute("aria-busy"),
                            label: form.querySelector("button").textContent,
                          };
                        }"""
                    )
                    if busy_state != {
                        "allDisabled": True,
                        "busy": "true",
                        "label": "Stopping backend…",
                    }:
                        failures.append(
                            f"{viewport_name}/dashboard action lock: "
                            f"{busy_state}"
                        )
                    page.screenshot(
                        path=str(
                            OUTPUT_DIRECTORY
                            / f"{viewport_name}-dashboard-busy.png"
                        ),
                        full_page=True,
                    )

            if console_errors:
                failures.extend(
                    f"{viewport_name} browser error: {item}"
                    for item in console_errors
                )
            context.close()
        browser.close()

    if failures:
        raise SystemExit("\n".join(failures))


if __name__ == "__main__":
    main()
