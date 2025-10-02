"""
Browser Automation Module

This module handles browser automation using Selenium for JavaScript-heavy websites
that require user interaction to access PDF download links.
"""

import logging
import time
from typing import List, Optional, Any
from urllib.parse import urljoin, urlparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException, 
    WebDriverException,
    ElementClickInterceptedException
)

logger = logging.getLogger(__name__)


class BrowserHandler:
    """Handles browser automation for interactive websites"""
    
    def __init__(self, headless: bool = True):
        self.driver: Optional[webdriver.Chrome] = None
        self.headless = headless
        self.wait: Optional[WebDriverWait] = None
        
    def start_browser(self):
        """Start browser instance when needed (lazy initialization)"""
        if not self.driver:
            logger.info("Starting browser instance...")
            options = Options()
            
            if self.headless:
                options.add_argument('--headless')
                logger.debug("Browser running in headless mode")
            
            # Chrome options for stability and compatibility
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-web-security')
            options.add_argument('--disable-features=VizDisplayCompositor')
            options.add_argument('--window-size=1920,1080')
            
            # User agent to appear more like a regular browser
            options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            try:
                self.driver = webdriver.Chrome(options=options)
                self.wait = WebDriverWait(self.driver, 10)
                logger.info("Browser started successfully")
            except Exception as e:
                logger.error(f"Failed to start browser: {e}")
                raise
            
    def handle_interactive_page(self, url: str) -> List[str]:
        """Handle pages requiring JavaScript/interaction to reveal PDF links"""
        if not self.driver:
            self.start_browser()
            
        pdf_links = []
        
        try:
            logger.info(f"Loading interactive page: {url}")
            self.driver.get(url)
            
            # Wait for page to load
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(2)  # Additional wait for JavaScript to execute
            
            # Try multiple strategies to find and reveal PDF links
            pdf_links.extend(self._find_existing_pdf_links())
            pdf_links.extend(self._click_interactive_elements())
            pdf_links.extend(self._execute_pdf_reveal_scripts())
            pdf_links.extend(self._handle_forms_and_modals())
            
            # Remove duplicates and convert relative URLs to absolute
            pdf_links = list(set(pdf_links))
            pdf_links = [urljoin(url, link) if not link.startswith('http') else link for link in pdf_links]
            
            logger.info(f"Found {len(pdf_links)} PDF links on interactive page")
            
        except Exception as e:
            logger.error(f"Error handling interactive page {url}: {e}")
            
        return pdf_links
        
    def _find_existing_pdf_links(self) -> List[str]:
        """Find PDF links that are already visible on the page"""
        pdf_links = []
        
        try:
            # Look for direct PDF links
            pdf_selectors = [
                'a[href$=".pdf"]',
                'a[href*=".pdf"]',
                'a[download*=".pdf"]',
                'a:contains("PDF")',
                'a:contains("Download")',
                'a[title*="PDF"]',
                'a[title*="Download"]'
            ]
            
            for selector in pdf_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector.replace(':contains', '[text*='))
                    for element in elements:
                        href = element.get_attribute('href')
                        if href and ('.pdf' in href.lower() or 'download' in href.lower()):
                            pdf_links.append(href)
                except:
                    continue
                    
        except Exception as e:
            logger.debug(f"Error finding existing PDF links: {e}")
            
        return pdf_links
        
    def _click_interactive_elements(self) -> List[str]:
        """Click on elements that might reveal PDF download links"""
        pdf_links = []
        
        # Common selectors for elements that might reveal PDFs
        clickable_selectors = [
            'button:contains("Download")',
            'button:contains("PDF")',
            'button:contains("View")',
            'button:contains("Show")',
            'a:contains("More")',
            'a:contains("View All")',
            'a:contains("Show All")',
            '.download-btn',
            '.pdf-btn',
            '.view-more',
            '.show-all'
        ]
        
        for selector in clickable_selectors:
            try:
                # Convert :contains to xpath for Selenium
                if ':contains' in selector:
                    text = selector.split(':contains("')[1].split('")')[0]
                    tag = selector.split(':contains')[0]
                    xpath = f"//{tag}[contains(text(), '{text}')]"
                    elements = self.driver.find_elements(By.XPATH, xpath)
                else:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in elements[:3]:  # Limit to first 3 elements
                    try:
                        # Scroll element into view
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                        time.sleep(0.5)
                        
                        # Try to click the element
                        element.click()
                        time.sleep(2)  # Wait for content to load
                        
                        # Look for new PDF links after clicking
                        new_links = self._find_existing_pdf_links()
                        pdf_links.extend(new_links)
                        
                    except (ElementClickInterceptedException, NoSuchElementException):
                        # Try JavaScript click if regular click fails
                        try:
                            self.driver.execute_script("arguments[0].click();", element)
                            time.sleep(2)
                            new_links = self._find_existing_pdf_links()
                            pdf_links.extend(new_links)
                        except:
                            continue
                    except Exception as e:
                        logger.debug(f"Error clicking element: {e}")
                        continue
                        
            except Exception as e:
                logger.debug(f"Error with selector {selector}: {e}")
                continue
                
        return pdf_links
        
    def _execute_pdf_reveal_scripts(self) -> List[str]:
        """Execute JavaScript to reveal hidden PDF URLs"""
        pdf_links = []
        
        # Common JavaScript patterns to reveal PDF links
        scripts = [
            # Look for data attributes that might contain PDF URLs
            """
            var links = [];
            var elements = document.querySelectorAll('[data-url*="pdf"], [data-href*="pdf"], [data-download*="pdf"]');
            elements.forEach(function(el) {
                var url = el.getAttribute('data-url') || el.getAttribute('data-href') || el.getAttribute('data-download');
                if (url) links.push(url);
            });
            return links;
            """,
            
            # Look for hidden links that might be revealed by JavaScript
            """
            var links = [];
            var hiddenElements = document.querySelectorAll('a[style*="display:none"], a[hidden]');
            hiddenElements.forEach(function(el) {
                var href = el.getAttribute('href');
                if (href && href.includes('.pdf')) links.push(href);
            });
            return links;
            """,
            
            # Trigger common JavaScript functions that might reveal PDFs
            """
            var links = [];
            if (typeof showDownloads === 'function') {
                try { showDownloads(); } catch(e) {}
            }
            if (typeof loadPDFs === 'function') {
                try { loadPDFs(); } catch(e) {}
            }
            if (typeof showAllDocuments === 'function') {
                try { showAllDocuments(); } catch(e) {}
            }
            return links;
            """
        ]
        
        for script in scripts:
            try:
                result = self.driver.execute_script(script)
                if result and isinstance(result, list):
                    pdf_links.extend(result)
                time.sleep(1)  # Wait between script executions
            except Exception as e:
                logger.debug(f"Error executing JavaScript: {e}")
                continue
                
        return pdf_links
        
    def _handle_forms_and_modals(self) -> List[str]:
        """Handle forms and modal dialogs that might contain PDF links"""
        pdf_links = []
        
        try:
            # Look for and handle common modal triggers
            modal_triggers = [
                'button[data-toggle="modal"]',
                'a[data-toggle="modal"]',
                '.modal-trigger',
                '.popup-trigger'
            ]
            
            for selector in modal_triggers:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements[:2]:  # Limit to first 2 modals
                        try:
                            element.click()
                            time.sleep(2)
                            
                            # Look for PDF links in the modal
                            modal_links = self._find_existing_pdf_links()
                            pdf_links.extend(modal_links)
                            
                            # Close modal if possible
                            close_buttons = self.driver.find_elements(By.CSS_SELECTOR, '.close, .modal-close, [data-dismiss="modal"]')
                            if close_buttons:
                                close_buttons[0].click()
                                time.sleep(1)
                                
                        except Exception as e:
                            logger.debug(f"Error handling modal: {e}")
                            continue
                            
                except Exception as e:
                    logger.debug(f"Error with modal selector {selector}: {e}")
                    continue
            
            # Handle simple forms (like terms acceptance)
            forms = self.driver.find_elements(By.TAG_NAME, 'form')
            for form in forms[:2]:  # Limit to first 2 forms
                try:
                    # Look for checkboxes (terms acceptance)
                    checkboxes = form.find_elements(By.CSS_SELECTOR, 'input[type="checkbox"]')
                    for checkbox in checkboxes:
                        if not checkbox.is_selected():
                            checkbox.click()
                    
                    # Look for submit buttons
                    submit_buttons = form.find_elements(By.CSS_SELECTOR, 'input[type="submit"], button[type="submit"], .submit-btn')
                    if submit_buttons:
                        submit_buttons[0].click()
                        time.sleep(3)
                        
                        # Look for PDF links after form submission
                        form_links = self._find_existing_pdf_links()
                        pdf_links.extend(form_links)
                        
                except Exception as e:
                    logger.debug(f"Error handling form: {e}")
                    continue
                    
        except Exception as e:
            logger.debug(f"Error handling forms and modals: {e}")
            
        return pdf_links
        
    def execute_javascript(self, script: str) -> Any:
        """Execute JavaScript to reveal hidden PDF URLs"""
        if not self.driver:
            self.start_browser()
            
        try:
            result = self.driver.execute_script(script)
            logger.debug(f"JavaScript executed successfully")
            return result
        except Exception as e:
            logger.error(f"Error executing JavaScript: {e}")
            return None
            
    def wait_for_element(self, selector: str, timeout: int = 10) -> bool:
        """Wait for element to appear on page"""
        if not self.driver:
            self.start_browser()
            
        try:
            wait = WebDriverWait(self.driver, timeout)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            return True
        except TimeoutException:
            logger.debug(f"Element {selector} not found within {timeout} seconds")
            return False
        except Exception as e:
            logger.error(f"Error waiting for element {selector}: {e}")
            return False
            
    def close_browser(self):
        """Clean up browser resources"""
        if self.driver:
            try:
                logger.info("Closing browser instance...")
                self.driver.quit()
                logger.info("Browser closed successfully")
            except Exception as e:
                logger.error(f"Error closing browser: {e}")
            finally:
                self.driver = None
                self.wait = None