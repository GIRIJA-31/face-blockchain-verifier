"""
face-blockchain-verifier
-------------------------
Automates a Google Lens reverse image search using Selenium + Microsoft Edge.

Requirements:
    pip install selenium webdriver-manager

Usage:
    Put your image in the "data" folder, e.g. data/bill gates.jpg
    Run this script, then type:  bill gates.jpg
"""

import os
import sys
import time
from urllib.parse import urlparse, parse_qs

from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    NoSuchWindowException,
)

try:
    import pyautogui
except ImportError:
    print("This version needs pyautogui: pip install pyautogui")
    sys.exit(1)

try:
    from webdriver_manager.microsoft import EdgeChromiumDriverManager
    AUTO_DRIVER = True
except ImportError:
    # Falls back to a msedgedriver.exe that's already on PATH
    AUTO_DRIVER = False


# --------------------------------------------------------------------------
# Driver setup
# --------------------------------------------------------------------------
def build_driver():
    options = EdgeOptions()
    options.add_argument("--start-maximized")

    # These two lines stop Google from easily detecting Selenium and serving
    # a broken/non-interactive page. This is the most common root cause of
    # "upload looks fine but nothing happens" on Google properties.
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0"
    )

    if AUTO_DRIVER:
        service = EdgeService(EdgeChromiumDriverManager().install())
        driver = webdriver.Edge(service=service, options=options)
    else:
        driver = webdriver.Edge(options=options)

    # Hide navigator.webdriver from the page's own JavaScript
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
        )
    except Exception:
        pass  # not fatal if CDP isn't available

    return driver


# --------------------------------------------------------------------------
# Wait for the modal itself to be fully mounted before touching anything.
# Grabbing the input too early is a common cause of "silently does nothing":
# React swaps the real input in shortly after mount, orphaning any element
# reference you grabbed before that happened.
# --------------------------------------------------------------------------
def wait_for_modal_ready(driver, timeout=20):
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located(
            (By.XPATH, "//*[contains(text(),'Drag an image') or contains(text(),'upload a file')]")
        )
    )


# --------------------------------------------------------------------------
# Upload logic - this is the key change. Writing into the hidden <input>
# directly gets silently rejected by Google (confirmed: input.files stayed
# empty after send_keys, even though a plain local test page worked fine -
# so this is Google specifically, not your environment). Instead, we click
# the real "upload a file" link, which opens the actual native Windows file
# picker, and drive THAT with pyautogui - a genuine OS-level interaction,
# indistinguishable from what a person does manually.
# --------------------------------------------------------------------------
def find_upload_link(driver, timeout=15):
    return WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, "//*[contains(text(),'upload a file')]"))
    )


def upload_via_native_dialog(driver, image_path, dialog_wait=2.5):
    link = find_upload_link(driver)
    try:
        link.click()
    except Exception:
        driver.execute_script("arguments[0].click();", link)

    # Give Windows time to actually open the file picker before we start typing
    time.sleep(dialog_wait)

    # The filename field is focused by default when the dialog opens
    pyautogui.write(image_path, interval=0.01)
    time.sleep(0.3)
    pyautogui.press("enter")


def upload_image_to_lens(driver, image_path, max_attempts=3):
    for attempt in range(1, max_attempts + 1):
        print(f"Upload attempt {attempt}/{max_attempts} (native file dialog)...")
        try:
            upload_via_native_dialog(driver, image_path)
        except TimeoutException:
            print("  Could not find the 'upload a file' link (page may have already moved past the upload step).")
            # If we can't find the link anymore, check whether we actually
            # already succeeded and just don't realize it yet.
            state = wait_for_attachment_or_results(driver, timeout=5)
            if state:
                print(f"  Already at '{state}' state - treating as success.")
                return True
            continue

        state = wait_for_attachment_or_results(driver, timeout=12)
        try:
            driver.save_screenshot("debug_after_attempt.png")
        except Exception:
            pass

        if state:
            print(f"  Confirmed: reached '{state}' state.")
            return True
        print("  Not confirmed yet, retrying...")

    return False


# --------------------------------------------------------------------------
# Confirms the file actually attached OR that the page has already jumped
# straight to real results (Google sometimes skips the visible "attached"
# preview entirely for fast-processing images - treating that as a
# separate failure caused false negatives). Every DOM read here is
# wrapped defensively since the page can mutate mid-check while it
# transitions between states.
# --------------------------------------------------------------------------
def wait_for_attachment_or_results(driver, timeout=12):
    start_url = driver.current_url
    wait = WebDriverWait(driver, timeout)

    def check(d):
        try:
            cur = d.current_url
        except Exception:
            return False
        if cur != start_url and (
            "vsrid=" in cur or "search?" in cur or "/lens/" in cur or "uploadbyurl" in cur
        ):
            return "results"

        try:
            drag_elements = d.find_elements(By.XPATH, "//*[contains(text(),'Drag an image here')]")
        except Exception:
            drag_elements = []

        placeholder_visible = False
        for el in drag_elements:
            try:
                if el.is_displayed():
                    placeholder_visible = True
                    break
            except StaleElementReferenceException:
                continue

        if placeholder_visible:
            return False

        try:
            imgs = d.find_elements(By.TAG_NAME, "img")
        except Exception:
            imgs = []
        for img in imgs:
            try:
                src = img.get_attribute("src") or ""
                if src.startswith("blob:") and img.is_displayed():
                    return "attached"
            except StaleElementReferenceException:
                continue
            except Exception:
                continue

        # No visible drag placeholder and no blob thumbnail - if the whole
        # "Search any image with Google Lens" heading is also gone, the
        # page has fully moved past the upload modal into results.
        try:
            heading_present = bool(
                d.find_elements(By.XPATH, "//*[contains(text(),'Search any image with Google Lens')]")
            )
        except Exception:
            heading_present = True  # be conservative if we can't tell

        if not heading_present and not drag_elements:
            return "results"

        return False

    try:
        return wait.until(check)
    except TimeoutException:
        return None


# --------------------------------------------------------------------------
# Waiting for the REAL result, not just trusting that upload "worked"
# --------------------------------------------------------------------------
def wait_for_lens_results(driver, timeout=45):
    start_url = driver.current_url
    wait = WebDriverWait(driver, timeout)

    def lens_has_results(drv):
        # 1) URL actually changed to something result-like
        if drv.current_url != start_url and (
            "search" in drv.current_url
            or "uploadbyurl" in drv.current_url
            or "/lens/" in drv.current_url
        ):
            return True
        # 2) The upload placeholder text is gone -> results panel replaced it
        try:
            drv.find_element(By.XPATH, "//*[contains(text(), 'Search any image with Google Lens')]")
            return False
        except NoSuchElementException:
            return True
        except Exception:
            return False

    wait.until(lens_has_results)


def extract_result_text(driver):
    xpaths = [
        "//div[contains(@class,'result')]",
        "//*[@id='res']",
        "//div[contains(@class,'search')]",
    ]
    texts = []
    for xp in xpaths:
        try:
            for el in driver.find_elements(By.XPATH, xp)[:5]:
                t = el.text.strip()
                if t:
                    texts.append(t)
        except Exception:
            pass

    if not texts:
        texts.append(driver.find_element(By.TAG_NAME, "body").text[:2000])

    seen, unique = set(), []
    for t in texts:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return "\n---\n".join(unique[:5])


# --------------------------------------------------------------------------
# Real match extraction. Google Lens results normally have a "Visual
# matches" (or "All" / "Exact matches") tab listing external pages that
# contain the image. We click that tab if present, then collect real
# external links - structural (tag + href pattern), not tied to fragile
# CSS class names, since those change constantly.
# --------------------------------------------------------------------------
SOCIAL_DOMAINS = (
    "twitter.com", "x.com", "instagram.com", "facebook.com",
    "linkedin.com", "pinterest.com", "tiktok.com", "reddit.com",
    "youtube.com",
)

# Google's own properties (any ccTLD/subdomain variant) and ad/analytics
# infrastructure - none of these are ever a real "matching post".
JUNK_DOMAIN_MARKERS = ("google.", "gstatic.com", "googleusercontent.com", "doubleclick.net")

# Generic nav-bar/footer link text Google shows on every results page -
# filtering by domain alone wasn't enough (google.co.in slipped through
# last time), so we also drop known UI labels regardless of domain.
JUNK_TITLES = {
    "images", "maps", "gmail", "search", "google apps", "about", "privacy",
    "terms", "settings", "sign in", "feedback", "help", "shopping", "news",
    "more", "videos", "books", "flights", "finance", "translate",
}


def is_junk_domain(domain):
    d = domain.lower()
    return any(marker in d for marker in JUNK_DOMAIN_MARKERS)


def unwrap_google_redirect(href):
    """
    Google often wraps real result links behind an internal redirect, e.g.
    google.com/imgres?imgurl=...&imgrefurl=<REAL SOURCE PAGE>. The real
    destination sits in a query param, not the visible domain - so a
    blanket 'any google.* domain is junk' filter was silently discarding
    every genuine match. This pulls the real URL out when present.
    Returns None if it's a google.* link with nothing extractable
    (a genuine internal/nav link), or the href unchanged if it's already
    an external URL.
    """
    parsed = urlparse(href)
    if "google." not in parsed.netloc.lower():
        return href

    qs = parse_qs(parsed.query)
    for key in ("imgrefurl", "url", "q"):
        values = qs.get(key)
        if values and values[0].startswith("http"):
            return values[0]
    return None


def click_matches_tab(driver, timeout=8):
    for label in ("Visual matches", "Exact matches", "All"):
        try:
            tab = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, f"//*[normalize-space(text())='{label}']"))
            )
            tab.click()
            # Wait for at least one plausible non-Google result link to
            # show up, rather than a blind fixed sleep - more reliable
            # and doesn't waste time if results load fast.
            try:
                WebDriverWait(driver, 6).until(
                    lambda d: any(
                        not is_junk_domain(urlparse(unwrap_google_redirect(href) or "").netloc)
                        for href in d.execute_script(
                            "return Array.from(document.querySelectorAll('a[href^=\"http\"]'))"
                            ".map(a => a.href);"
                        )
                        if unwrap_google_redirect(href)
                    )
                )
            except TimeoutException:
                pass  # proceed with whatever we have - better than nothing
            return label
        except TimeoutException:
            continue
    return None


def extract_matches(driver, max_results=10):
    """
    Returns a list of {url, title, domain} dicts for external (non-Google)
    links found on the results page - these are the candidate "matching
    posts" the task asks for.
    """
    clicked_tab = click_matches_tab(driver)

    raw_links = driver.execute_script(
        """
        return Array.from(document.querySelectorAll('a[href^="http"]'))
            .map(a => ({
                url: a.href,
                title: (a.innerText || a.getAttribute('aria-label') || '').trim()
            }));
        """
    )

    seen_urls = set()
    matches = []
    for link in raw_links:
        raw_url = link.get("url", "")
        title = (link.get("title") or "").strip()
        if not raw_url:
            continue

        url = unwrap_google_redirect(raw_url)
        if not url or url in seen_urls:
            continue

        domain = urlparse(url).netloc
        if is_junk_domain(domain):
            continue
        if title.lower() in JUNK_TITLES:
            continue

        seen_urls.add(url)
        matches.append({"url": url, "title": title, "domain": domain})
        if len(matches) >= max_results:
            break

    if matches:
        return clicked_tab, matches

    # Fallback: no real <a href> links found at all - these cards are
    # JS-driven, not anchors. Parse the structured (source, headline)
    # text instead; the task allows "text or metadata" as valid
    # discovered data, not only a clickable URL.
    text = extract_result_text(driver)
    text_entries = parse_entries_from_text(text)
    return clicked_tab, text_entries[:max_results]


def choose_best_match(matches):
    """Prefer a known social-media source; otherwise take the first result."""
    def is_social(domain_or_source):
        s = (domain_or_source or "").lower().strip()
        if s in ("x", "x.com"):
            return True
        return any(hint in s for hint in ("twitter", "instagram", "facebook", "linkedin", "pinterest", "tiktok", "reddit", "youtube"))

    for m in matches:
        if is_social(m.get("domain")):
            return m
    return matches[0] if matches else None


# Nav-bar / UI labels that show up as short "lines" in the page text but
# are never a real source name - filtered out of the text-based fallback.
NAV_JUNK_SOURCES = {
    "skip to main content", "accessibility help", "sign in", "ai mode", "all",
    "exact matches", "visual matches", "feedback", "search results",
    "related search", "see exact matches", "images", "news", "videos",
    "shopping", "maps", "books", "flights", "finance", "translate",
}


def parse_entries_from_text(text):
    """
    Google's result cards here aren't plain <a href> elements (confirmed:
    zero found even after unwrapping redirects), but the rendered text is
    clearly structured as repeating (source name, headline) pairs. This
    parses that structure directly - the task explicitly allows "text or
    metadata" as the discovered data, not only a clickable URL.
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    entries = []
    i = 0
    n = len(lines)
    while i < n - 1:
        source, title = lines[i], lines[i + 1]
        if (
            len(source) <= 30
            and source.lower() not in NAV_JUNK_SOURCES
            and len(title) > 20
        ):
            entries.append({"url": None, "title": title, "domain": source})
            i += 2
        else:
            i += 1
    return entries


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    image_name = input("Enter image name to search: ").strip()
    image_path = os.path.abspath(os.path.join("data", image_name))

    if not os.path.isfile(image_path):
        print(f"File not found: {image_path}")
        sys.exit(1)

    driver = build_driver()
    try:
        driver.get("https://lens.google.com/")

        print("Waiting for the upload modal to fully load...")
        wait_for_modal_ready(driver)

        print("Uploading image via the real Windows file dialog (pyautogui)...")
        attached = upload_image_to_lens(driver, image_path)

        if not attached:
            driver.switch_to.default_content()
            driver.save_screenshot("debug_attachment_failed.png")
            print("The image did NOT visibly attach after several attempts.")
            print("Saved a screenshot to debug_attachment_failed.png - open it to see the popup's real state.")
            print("Current URL:", driver.current_url)
            return

        print("Attachment confirmed. Waiting for Google Lens to process it...")
        wait_for_lens_results(driver)

        print("Google Lens finished processing.")
        print("Final URL:", driver.current_url)

        print("\nLooking for real matching pages/posts...")
        clicked_tab, matches = extract_matches(driver)
        if clicked_tab:
            print(f"(opened '{clicked_tab}' tab)")

        if matches:
            print(f"\nFound {len(matches)} matching result(s):")
            for m in matches:
                if m.get("url"):
                    print(f"  - [{m['domain']}] {m['title'][:60]!r} -> {m['url']}")
                else:
                    print(f"  - [{m['domain']}] {m['title'][:80]!r} (no direct link, text-based match)")
            best = choose_best_match(matches)
            if best.get("url"):
                print(f"\nBest match chosen: {best['url']}")
            else:
                print(f"\nBest match chosen: [{best['domain']}] {best['title']}")
        else:
            print("No matches found at all - falling back to raw page text:")
            print(extract_result_text(driver))

    except TimeoutException as e:
        driver.switch_to.default_content()
        driver.save_screenshot("debug_timeout.png")
        print(f"Timed out: {e}")
        print("Current URL:", driver.current_url)
        print("Saved a screenshot to debug_timeout.png for troubleshooting.")
        print("This usually means Google detected automated access, or the page layout changed.")
    except NoSuchWindowException:
        print("The browser window closed unexpectedly (either it crashed or was closed manually).")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        try:
            input("\nPress Enter to close the browser...")
        except Exception:
            pass
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()