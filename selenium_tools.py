"""
Selenium Tools for SuperCoder - Browser Automation
"""
import os
import time
import base64
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

# Global browser sessions
_browser_sessions = {}
_session_counter = 0

def _get_driver(browser: str = "chrome", headless: bool = False):
    """Get a WebDriver instance"""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service as ChromeService
        from selenium.webdriver.firefox.service import Service as FirefoxService
        from selenium.webdriver.edge.service import Service as EdgeService
        from webdriver_manager.chrome import ChromeDriverManager
        from webdriver_manager.firefox import GeckoDriverManager
        from webdriver_manager.microsoft import EdgeChromiumDriverManager
        
        if browser.lower() == "chrome":
            options = webdriver.ChromeOptions()
            if headless:
                options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            service = ChromeService(ChromeDriverManager().install())
            return webdriver.Chrome(service=service, options=options)
        
        elif browser.lower() == "firefox":
            options = webdriver.FirefoxOptions()
            if headless:
                options.add_argument("--headless")
            service = FirefoxService(GeckoDriverManager().install())
            return webdriver.Firefox(service=service, options=options)
        
        elif browser.lower() == "edge":
            options = webdriver.EdgeOptions()
            if headless:
                options.add_argument("--headless=new")
            service = EdgeService(EdgeChromiumDriverManager().install())
            return webdriver.Edge(service=service, options=options)
        
        else:
            return {"error": f"Unsupported browser: {browser}. Use 'chrome', 'firefox', or 'edge'"}
    
    except ImportError as e:
        return {"error": f"Selenium not installed. Run: pip install selenium webdriver-manager"}
    except Exception as e:
        return {"error": f"Failed to start browser: {str(e)}"}


def selenium_start_browser(browser: str = "chrome", headless: bool = False) -> Dict[str, Any]:
    """
    Start a browser session.
    
    Args:
        browser: Browser type ('chrome', 'firefox', 'edge')
        headless: Run without GUI (default False)
    
    Returns:
        session_id: Unique browser session identifier
        browser: Browser type
        headless: Whether running headless
    """
    global _session_counter
    
    try:
        driver = _get_driver(browser, headless)
        
        if isinstance(driver, dict) and "error" in driver:
            return driver
        
        _session_counter += 1
        session_id = _session_counter
        
        _browser_sessions[session_id] = {
            "driver": driver,
            "browser": browser,
            "headless": headless,
            "created_at": datetime.now().isoformat(),
            "current_url": "about:blank"
        }
        
        return {
            "session_id": session_id,
            "browser": browser,
            "headless": headless,
            "message": f"Browser session {session_id} started successfully"
        }
    
    except Exception as e:
        return {"error": f"Failed to start browser: {str(e)}"}


def selenium_close_browser(session_id: int) -> Dict[str, Any]:
    """
    Close a browser session.
    
    Args:
        session_id: Browser session ID
    
    Returns:
        success: Boolean
        message: Status message
    """
    try:
        if session_id not in _browser_sessions:
            return {"error": f"Session {session_id} not found"}
        
        session = _browser_sessions[session_id]
        session["driver"].quit()
        del _browser_sessions[session_id]
        
        return {
            "success": True,
            "message": f"Browser session {session_id} closed"
        }
    
    except Exception as e:
        return {"error": f"Failed to close browser: {str(e)}"}


def selenium_list_sessions() -> Dict[str, Any]:
    """
    List all active browser sessions.
    
    Returns:
        sessions: List of active sessions with details
    """
    sessions = []
    for sid, session in _browser_sessions.items():
        sessions.append({
            "session_id": sid,
            "browser": session["browser"],
            "headless": session["headless"],
            "current_url": session["current_url"],
            "created_at": session["created_at"]
        })
    
    return {
        "active_sessions": len(sessions),
        "sessions": sessions
    }


def selenium_navigate(session_id: int, url: str) -> Dict[str, Any]:
    """
    Navigate to a URL.
    
    Args:
        session_id: Browser session ID
        url: URL to navigate to
    
    Returns:
        current_url: Current URL after navigation
        title: Page title
    """
    try:
        if session_id not in _browser_sessions:
            return {"error": f"Session {session_id} not found"}
        
        session = _browser_sessions[session_id]
        driver = session["driver"]
        
        # Add protocol if missing
        if not url.startswith(("http://", "https://", "file://", "about:")):
            url = "https://" + url
        
        driver.get(url)
        
        # Wait for page to load
        time.sleep(1)
        
        session["current_url"] = driver.current_url
        
        return {
            "session_id": session_id,
            "current_url": driver.current_url,
            "title": driver.title,
            "message": f"Navigated to {url}"
        }
    
    except Exception as e:
        return {"error": f"Navigation failed: {str(e)}"}


def selenium_click(session_id: int, selector: str, selector_type: str = "css") -> Dict[str, Any]:
    """
    Click an element.
    
    Args:
        session_id: Browser session ID
        selector: Element selector (CSS selector, XPath, ID, etc.)
        selector_type: Type of selector ('css', 'xpath', 'id', 'name', 'class', 'tag')
    
    Returns:
        success: Boolean
        element_text: Text content of clicked element
    """
    try:
        if session_id not in _browser_sessions:
            return {"error": f"Session {session_id} not found"}
        
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        session = _browser_sessions[session_id]
        driver = session["driver"]
        
        # Map selector type to By constant
        by_map = {
            "css": By.CSS_SELECTOR,
            "xpath": By.XPATH,
            "id": By.ID,
            "name": By.NAME,
            "class": By.CLASS_NAME,
            "tag": By.TAG_NAME
        }
        
        if selector_type not in by_map:
            return {"error": f"Invalid selector_type: {selector_type}. Use: {list(by_map.keys())}"}
        
        by = by_map[selector_type]
        
        # Wait for element to be clickable
        element = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((by, selector))
        )
        
        element_text = element.text
        element.click()
        
        # Wait a bit after click
        time.sleep(0.5)
        
        return {
            "success": True,
            "element_text": element_text,
            "current_url": driver.current_url,
            "message": f"Clicked element: {selector}"
        }
    
    except Exception as e:
        return {"error": f"Click failed: {str(e)}"}


def selenium_type(session_id: int, selector: str, text: str, selector_type: str = "css", clear_first: bool = True) -> Dict[str, Any]:
    """
    Type text into an input field.
    
    Args:
        session_id: Browser session ID
        selector: Element selector
        text: Text to type
        selector_type: Type of selector ('css', 'xpath', 'id', 'name')
        clear_first: Clear field before typing (default True)
    
    Returns:
        success: Boolean
        message: Status message
    """
    try:
        if session_id not in _browser_sessions:
            return {"error": f"Session {session_id} not found"}
        
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        session = _browser_sessions[session_id]
        driver = session["driver"]
        
        by_map = {
            "css": By.CSS_SELECTOR,
            "xpath": By.XPATH,
            "id": By.ID,
            "name": By.NAME,
            "class": By.CLASS_NAME
        }
        
        if selector_type not in by_map:
            return {"error": f"Invalid selector_type: {selector_type}"}
        
        by = by_map[selector_type]
        
        # Wait for element
        element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((by, selector))
        )
        
        if clear_first:
            element.clear()
        
        element.send_keys(text)
        
        return {
            "success": True,
            "message": f"Typed text into element: {selector}"
        }
    
    except Exception as e:
        return {"error": f"Type failed: {str(e)}"}


def selenium_get_element(session_id: int, selector: str, selector_type: str = "css") -> Dict[str, Any]:
    """
    Get element properties.
    
    Args:
        session_id: Browser session ID
        selector: Element selector
        selector_type: Type of selector
    
    Returns:
        text: Element text content
        tag_name: HTML tag name
        attributes: Element attributes
        location: Element position (x, y)
        size: Element size (width, height)
        visible: Whether element is visible
    """
    try:
        if session_id not in _browser_sessions:
            return {"error": f"Session {session_id} not found"}
        
        from selenium.webdriver.common.by import By
        
        session = _browser_sessions[session_id]
        driver = session["driver"]
        
        by_map = {
            "css": By.CSS_SELECTOR,
            "xpath": By.XPATH,
            "id": By.ID,
            "name": By.NAME,
            "class": By.CLASS_NAME,
            "tag": By.TAG_NAME
        }
        
        by = by_map.get(selector_type, By.CSS_SELECTOR)
        element = driver.find_element(by, selector)
        
        # Get common attributes
        attributes = {}
        for attr in ["id", "class", "name", "href", "src", "value", "placeholder", "type"]:
            val = element.get_attribute(attr)
            if val:
                attributes[attr] = val
        
        return {
            "text": element.text,
            "tag_name": element.tag_name,
            "attributes": attributes,
            "location": element.location,
            "size": element.size,
            "visible": element.is_displayed(),
            "enabled": element.is_enabled()
        }
    
    except Exception as e:
        return {"error": f"Get element failed: {str(e)}"}


def selenium_execute_script(session_id: int, script: str) -> Dict[str, Any]:
    """
    Execute JavaScript in the browser.
    
    Args:
        session_id: Browser session ID
        script: JavaScript code to execute
    
    Returns:
        result: Return value from JavaScript
    """
    try:
        if session_id not in _browser_sessions:
            return {"error": f"Session {session_id} not found"}
        
        session = _browser_sessions[session_id]
        driver = session["driver"]
        
        result = driver.execute_script(script)
        
        return {
            "success": True,
            "result": result,
            "message": "Script executed successfully"
        }
    
    except Exception as e:
        return {"error": f"Script execution failed: {str(e)}"}


def selenium_screenshot(session_id: int, save_path: str = None, element_selector: str = None, full_page: bool = False) -> Dict[str, Any]:
    """
    Take a screenshot of the browser.
    
    Args:
        session_id: Browser session ID
        save_path: Path to save screenshot (default: auto-generated in .supercoder/screenshots/)
        element_selector: Optional CSS selector to screenshot specific element
        full_page: Capture entire scrollable page (default False)
    
    Returns:
        screenshot_path: Path to saved screenshot
        width: Image width
        height: Image height
        size_bytes: File size
    """
    try:
        if session_id not in _browser_sessions:
            return {"error": f"Session {session_id} not found"}
        
        from selenium.webdriver.common.by import By
        
        session = _browser_sessions[session_id]
        driver = session["driver"]
        
        # Create screenshots directory
        screenshots_dir = Path(".supercoder/screenshots")
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename if not provided
        if save_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = screenshots_dir / f"screenshot_{session_id}_{timestamp}.png"
        else:
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Take screenshot
        if element_selector:
            # Screenshot specific element
            element = driver.find_element(By.CSS_SELECTOR, element_selector)
            element.screenshot(str(save_path))
        elif full_page:
            # Full page screenshot (requires scrolling)
            # Get page dimensions
            total_height = driver.execute_script("return document.body.scrollHeight")
            viewport_height = driver.execute_script("return window.innerHeight")
            
            # For now, just take regular screenshot
            # Full page stitching would require PIL
            driver.save_screenshot(str(save_path))
        else:
            # Regular viewport screenshot
            driver.save_screenshot(str(save_path))
        
        # Get image info
        from PIL import Image
        img = Image.open(save_path)
        width, height = img.size
        size_bytes = save_path.stat().st_size
        
        return {
            "screenshot_path": str(save_path),
            "width": width,
            "height": height,
            "size_bytes": size_bytes,
            "size_human": _human_readable_size(size_bytes),
            "full_page": full_page,
            "element": element_selector,
            "message": f"Screenshot saved to {save_path}"
        }
    
    except ImportError:
        return {"error": "PIL (Pillow) not installed. Run: pip install Pillow"}
    except Exception as e:
        return {"error": f"Screenshot failed: {str(e)}"}


def selenium_wait_for_element(session_id: int, selector: str, selector_type: str = "css", timeout: int = 10) -> Dict[str, Any]:
    """
    Wait for an element to appear.
    
    Args:
        session_id: Browser session ID
        selector: Element selector
        selector_type: Type of selector
        timeout: Maximum wait time in seconds (default 10)
    
    Returns:
        found: Boolean
        time_waited: Seconds waited
    """
    try:
        if session_id not in _browser_sessions:
            return {"error": f"Session {session_id} not found"}
        
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        session = _browser_sessions[session_id]
        driver = session["driver"]
        
        by_map = {
            "css": By.CSS_SELECTOR,
            "xpath": By.XPATH,
            "id": By.ID,
            "name": By.NAME,
            "class": By.CLASS_NAME
        }
        
        by = by_map.get(selector_type, By.CSS_SELECTOR)
        
        start_time = time.time()
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, selector))
        )
        time_waited = time.time() - start_time
        
        return {
            "found": True,
            "time_waited": round(time_waited, 2),
            "message": f"Element found after {time_waited:.2f} seconds"
        }
    
    except Exception as e:
        return {
            "found": False,
            "error": f"Element not found within {timeout} seconds: {str(e)}"
        }


def selenium_get_page_source(session_id: int) -> Dict[str, Any]:
    """
    Get the HTML source of the current page.
    
    Args:
        session_id: Browser session ID
    
    Returns:
        html: Page HTML source
        length: HTML length in characters
    """
    try:
        if session_id not in _browser_sessions:
            return {"error": f"Session {session_id} not found"}
        
        session = _browser_sessions[session_id]
        driver = session["driver"]
        
        html = driver.page_source
        
        return {
            "html": html,
            "length": len(html),
            "current_url": driver.current_url,
            "title": driver.title
        }
    
    except Exception as e:
        return {"error": f"Failed to get page source: {str(e)}"}


def _human_readable_size(size_bytes: int) -> str:
    """Convert bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"
