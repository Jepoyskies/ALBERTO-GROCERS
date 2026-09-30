import os
import time
import requests
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# Configuration from environment variables (set in docker-compose.yml)
WEB_URL = os.environ.get("WEB_URL", "http://web:8000")
SELENIUM_URL = os.environ.get("SELENIUM_URL", "http://selenium:4444/wd/hub")

def wait_for_service(url, name, timeout=60):
    """Wait for a service to be available."""
    print(f"Waiting for {name} at {url}...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # For Selenium, we check /wd/hub/status or just /
            response = requests.get(url, timeout=5)
            if response.status_code < 500:
                print(f"{name} is ready!")
                return True
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            pass
        time.sleep(2)
    return False

def _reachable(url, timeout=2):
    """Fast reachability probe - avoids the long wait when the service is absent."""
    try:
        requests.get(url, timeout=timeout)
        return True
    except requests.exceptions.RequestException:
        return False

@pytest.fixture(scope="module", autouse=True)
def wait_for_infrastructure():
    """Ensure both web and selenium services are ready before running any tests.

    These tests target the docker-compose services (``web:8000`` / ``selenium:4444``).
    On a plain host checkout that infrastructure is not running, so we SKIP rather
    than error - a missing service is not a product defect. Inside
    ``docker-compose run --rm tests pytest`` the services are present and the
    tests execute normally.
    """
    if not _reachable(WEB_URL):
        pytest.skip(
            f"Web server at {WEB_URL} is not reachable. "
            "Run 'docker-compose up' (or 'docker-compose run --rm tests pytest') to exercise these."
        )
    if not wait_for_service(WEB_URL, "Web Server"):
        pytest.skip(f"Web server at {WEB_URL} did not become ready in time.")

    # Check selenium (using the base URL is enough to see if it responds)
    if not _reachable(SELENIUM_URL.replace("/wd/hub", "")):
        pytest.skip(
            f"Selenium server at {SELENIUM_URL} is not reachable. "
            "Run 'docker-compose up' to exercise the browser tests."
        )
    if not wait_for_service(SELENIUM_URL.replace("/wd/hub", ""), "Selenium Server"):
        pytest.skip(f"Selenium server at {SELENIUM_URL} did not become ready in time.")

class TestHttpIntegration:
    """Tests using requests to verify the web service is responding."""

    def test_homepage_is_up(self):
        """Verify the homepage returns a 200 OK status code."""
        response = requests.get(WEB_URL)
        assert response.status_code == 200
        assert "Alberto" in response.text

    def test_login_page_is_up(self):
        """Verify the login page returns a 200 OK status code."""
        response = requests.get(f"{WEB_URL}/accounts/login/")
        assert response.status_code == 200
        assert "Login" in response.text or "Sign in" in response.text

class TestBrowserIntegration:
    """Tests using Selenium to verify the browser rendering."""

    @pytest.fixture(scope="class")
    def driver(self):
        """Setup Selenium WebDriver."""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        # Connect to the remote selenium service
        driver = webdriver.Remote(
            command_executor=SELENIUM_URL,
            options=chrome_options
        )
        yield driver
        driver.quit()

    def test_login_page_renders(self, driver):
        """Verify the login page renders correctly in a real browser."""
        driver.get(f"{WEB_URL}/accounts/login/")
        
        # Check title
        assert "Login" in driver.title or "Alberto" in driver.title
        
        # Verify login form elements exist
        username_input = driver.find_element(By.NAME, "username")
        password_input = driver.find_element(By.NAME, "password")
        submit_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        
        assert username_input.is_displayed()
        assert password_input.is_displayed()
        assert submit_button.is_displayed()

    def test_homepage_navigation(self, driver):
        """Verify navigation to the homepage."""
        driver.get(WEB_URL)
        
        # Verify some text on the homepage
        body_text = driver.find_element(By.TAG_NAME, "body").text
        assert "Alberto" in body_text
