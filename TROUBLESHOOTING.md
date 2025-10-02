# HK PDF Crawler - Troubleshooting Guide

This guide covers common issues and their solutions when using the HK Government PDF Crawler.

## Quick Diagnostics

### 1. Test Basic Functionality

```bash
# Test help system
python main.py --help

# Test configuration parsing
python main.py --config config.yaml --dry-run

# Test with debug logging
python main.py --config config.yaml --dry-run --log-level DEBUG
```

### 2. Check Dependencies

```bash
# Verify Python version (3.8+ required)
python --version

# Check installed packages
pip list | grep -E "(requests|beautifulsoup4|selenium|pyyaml|boto3|tqdm)"

# Test Selenium/ChromeDriver
python -c "from selenium import webdriver; driver = webdriver.Chrome(); driver.quit(); print('Browser automation OK')"
```

## Common Issues and Solutions

### Installation and Setup Issues

#### Issue: `ModuleNotFoundError: No module named 'requests'`

**Cause**: Missing Python dependencies

**Solution**:
```bash
# Install all required dependencies
pip install -r requirements.txt

# Or install individually
pip install requests beautifulsoup4 selenium pyyaml boto3 tqdm lxml
```

#### Issue: `selenium.common.exceptions.WebDriverException: 'chromedriver' executable needs to be in PATH`

**Cause**: ChromeDriver not installed or not in PATH

**Solutions**:

**Option 1 - Install via package manager (Recommended)**:
```bash
# macOS with Homebrew
brew install chromedriver

# Ubuntu/Debian
sudo apt-get install chromium-chromedriver

# Windows with Chocolatey
choco install chromedriver
```

**Option 2 - Manual installation**:
1. Download ChromeDriver from https://chromedriver.chromium.org/
2. Extract and place in PATH or project directory
3. Make executable: `chmod +x chromedriver`

**Option 3 - Use webdriver-manager (automatic)**:
```bash
pip install webdriver-manager
```

#### Issue: `Chrome version mismatch`

**Cause**: ChromeDriver version doesn't match Chrome browser version

**Solution**:
```bash
# Check Chrome version
google-chrome --version  # Linux
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --version  # macOS

# Download matching ChromeDriver from:
# https://chromedriver.chromium.org/downloads

# Or use webdriver-manager for automatic management
pip install webdriver-manager
```

### Configuration Issues

#### Issue: `FileNotFoundError: Configuration file not found`

**Cause**: Config file path is incorrect

**Solutions**:
```bash
# Check file exists
ls -la config.yaml

# Use absolute path
python main.py --config /full/path/to/config.yaml

# Use provided sample configs
python main.py --config config-sample-basic.yaml
```

#### Issue: `yaml.YAMLError: Failed to parse YAML configuration`

**Cause**: Invalid YAML syntax

**Solutions**:
```bash
# Validate YAML syntax online: https://yamlchecker.com/
# Or use Python to check:
python -c "import yaml; yaml.safe_load(open('config.yaml'))"

# Common YAML issues:
# - Incorrect indentation (use spaces, not tabs)
# - Missing quotes around URLs with special characters
# - Inconsistent list formatting
```

**Example of correct YAML formatting**:
```yaml
departments:
  buildings_department:  # Correct indentation
    name: "Buildings Department"  # Quotes for strings with spaces
    seed_urls:
      - "https://example.com"  # List items with dashes
    max_depth: 3  # Numbers without quotes
```

#### Issue: `ValueError: No departments found in markdown file`

**Cause**: Markdown file format not recognized

**Solution**:
Ensure markdown file follows this format:
```markdown
## 1. Department Name (ABBR):
1. **Description**: https://example.com/url1
2. **Another**: https://example.com/url2

## 2. Another Department:
1. **Resource**: https://example.com/url3
```

### Network and Access Issues

#### Issue: `requests.exceptions.ConnectionError: Failed to establish a new connection`

**Cause**: Network connectivity issues or blocked access

**Solutions**:
```bash
# Test basic connectivity
curl -I https://www.bd.gov.hk/

# Check if behind corporate firewall/proxy
# Configure proxy in config.yaml or environment variables:
export HTTP_PROXY=http://proxy.company.com:8080
export HTTPS_PROXY=http://proxy.company.com:8080

# Test with different user agent
# Edit config.yaml:
settings:
  user_agent: "Mozilla/5.0 (compatible; Research Bot)"
```

#### Issue: `HTTP 429: Too Many Requests`

**Cause**: Rate limiting by the website

**Solutions**:
```yaml
# Increase delays in config.yaml
settings:
  delay_between_requests: 3.0  # Increase from default 1.5
  max_concurrent_downloads: 1  # Reduce concurrency

# Or run with smaller batches
python main.py --config config.yaml --departments buildings_department
```

#### Issue: `HTTP 403: Forbidden` or `HTTP 401: Unauthorized`

**Cause**: Website blocking automated access

**Solutions**:
```yaml
# Enable browser automation
settings:
  enable_browser_automation: true

# Use more realistic user agent
settings:
  user_agent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# Increase delays to appear more human-like
settings:
  delay_between_requests: 2.5
```

#### Issue: `requests.exceptions.Timeout`

**Cause**: Slow network or server response

**Solutions**:
```yaml
# Increase timeout in config.yaml
settings:
  request_timeout: 60  # Increase from default 30 seconds

# Or for specific slow sites, reduce concurrent downloads
settings:
  max_concurrent_downloads: 1
```

### Browser Automation Issues

#### Issue: `selenium.common.exceptions.TimeoutException`

**Cause**: Page taking too long to load or element not found

**Solutions**:
```bash
# Run with visible browser for debugging
# Temporarily set headless=False in browser.py

# Check if site requires specific browser settings
# Some government sites may need:
# - Specific screen resolution
# - JavaScript enabled
# - Cookies enabled
```

#### Issue: Browser opens but doesn't navigate properly

**Cause**: JavaScript errors or site compatibility issues

**Solutions**:
```bash
# Test manually with visible browser
# Edit browser.py temporarily: headless=False

# Check browser console for JavaScript errors
# Some sites may require:
# - Specific Chrome version
# - Additional Chrome flags
# - Different browser (Firefox)
```

#### Issue: `selenium.common.exceptions.WebDriverException: unknown error: Chrome failed to start`

**Cause**: Chrome/Chromium not properly installed or accessible

**Solutions**:
```bash
# Install Chrome/Chromium
# Ubuntu: sudo apt-get install chromium-browser
# macOS: brew install --cask google-chrome
# Windows: Download from google.com/chrome

# For headless servers, install headless Chrome:
# Ubuntu: sudo apt-get install chromium-browser --no-install-recommends

# Set Chrome path if non-standard installation:
export CHROME_EXECUTABLE_PATH=/path/to/chrome
```

### Storage and File Issues

#### Issue: `PermissionError: [Errno 13] Permission denied`

**Cause**: Insufficient permissions for download directory

**Solutions**:
```bash
# Check and fix directory permissions
ls -la downloads/
chmod 755 downloads/
sudo chown $USER:$USER downloads/

# Or use different directory
mkdir ~/pdf-downloads
# Update config.yaml:
storage:
  local_path: "~/pdf-downloads"
```

#### Issue: `OSError: [Errno 28] No space left on device`

**Cause**: Insufficient disk space

**Solutions**:
```bash
# Check disk space
df -h

# Clean up old downloads or use S3-only mode:
storage:
  local_path: null  # No local storage
  s3_enabled: true
  s3_bucket: "your-bucket"

# Or use external drive:
storage:
  local_path: "/external/drive/downloads"
```

### AWS S3 Issues

#### Issue: `botocore.exceptions.NoCredentialsError: Unable to locate credentials`

**Cause**: AWS credentials not configured

**Solutions**:
```bash
# Option 1: AWS CLI
aws configure
# Enter: Access Key ID, Secret Access Key, Region, Output format

# Option 2: Environment variables
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1

# Option 3: IAM roles (for EC2)
# No configuration needed if running on EC2 with proper IAM role

# Test credentials
aws s3 ls
```

#### Issue: `botocore.exceptions.ClientError: The specified bucket does not exist`

**Cause**: S3 bucket doesn't exist or wrong name

**Solutions**:
```bash
# Create bucket
aws s3 mb s3://your-bucket-name

# Check bucket name in config.yaml
storage:
  s3_bucket: "correct-bucket-name"  # Must match exactly

# List your buckets
aws s3 ls
```

#### Issue: `botocore.exceptions.ClientError: Access Denied`

**Cause**: Insufficient S3 permissions

**Solutions**:
```bash
# Check IAM permissions - need at least:
# - s3:PutObject
# - s3:GetObject
# - s3:ListBucket

# Test with AWS CLI
aws s3 cp test.txt s3://your-bucket/test.txt
aws s3 rm s3://your-bucket/test.txt
```

### PDF Detection and Download Issues

#### Issue: `No PDFs found on known PDF sites`

**Cause**: PDF detection logic not finding links

**Solutions**:
```bash
# Enable browser automation for JavaScript sites
settings:
  enable_browser_automation: true

# Run with debug logging to see what's happening
python main.py --config config.yaml --log-level DEBUG

# Check if site structure changed
# Manually visit the URLs to verify PDFs exist

# Try with different user agent
settings:
  user_agent: "Mozilla/5.0 (compatible; PDF Crawler)"
```

#### Issue: `Downloaded content is not a valid PDF file`

**Cause**: Server returning HTML error pages instead of PDFs

**Solutions**:
```bash
# Check what's actually being downloaded
# Look in downloads directory for files with .pdf extension
# Open them in text editor to see if they're HTML

# Common causes:
# - Login required
# - JavaScript required
# - Rate limiting returning error pages

# Enable browser automation
settings:
  enable_browser_automation: true

# Increase delays
settings:
  delay_between_requests: 2.0
```

#### Issue: `Many download failures with network errors`

**Cause**: Unstable network or server issues

**Solutions**:
```bash
# Reduce concurrent downloads
settings:
  max_concurrent_downloads: 1

# Increase timeouts and delays
settings:
  request_timeout: 60
  delay_between_requests: 3.0

# Run in smaller batches
python main.py --config config.yaml --departments buildings_department
```

## Performance Issues

### Issue: Crawling is very slow

**Solutions**:
```yaml
# Increase concurrency (carefully)
settings:
  max_concurrent_downloads: 5  # But watch for rate limiting

# Reduce delays (carefully)
settings:
  delay_between_requests: 1.0  # But watch for blocking

# Limit scope
departments:
  your_department:
    max_depth: 2  # Reduce from 3
    max_pages: 200  # Reduce from 500
    time_limit: 900  # 15 minutes instead of 30
```

### Issue: High memory usage

**Solutions**:
```yaml
# Reduce concurrent downloads
settings:
  max_concurrent_downloads: 2

# Process departments one at a time
python main.py --config config.yaml --departments buildings_department
python main.py --config config.yaml --departments labour_department
```

### Issue: Browser automation is slow

**Solutions**:
```yaml
# Disable browser automation for sites that don't need it
settings:
  enable_browser_automation: false

# Or use it selectively by running dry-run first to identify which sites need it
python main.py --config config.yaml --dry-run
```

## Debugging Techniques

### Enable Detailed Logging

```bash
# Maximum verbosity
python main.py --config config.yaml --log-level DEBUG --log-file debug.log

# Then examine the log file
tail -f debug.log
grep ERROR debug.log
grep WARNING debug.log
```

### Test Individual Components

```bash
# Test configuration parsing only
python -c "from config import load_config; print(load_config('config.yaml'))"

# Test URL discovery only
python -c "
from discovery import URLDiscovery
import requests
session = requests.Session()
discovery = URLDiscovery(session)
links = discovery.find_pdf_links('https://www.bd.gov.hk/en/resources/')
print(f'Found {len(links)} PDF links')
"

# Test browser automation
python -c "
from browser import BrowserHandler
browser = BrowserHandler(headless=False)  # Visible for debugging
browser.start_browser()
browser.driver.get('https://www.bd.gov.hk/')
input('Press Enter to close browser...')
browser.close_browser()
"
```

### Dry-Run Analysis

Always start with dry-run to identify issues:

```bash
# Analyze without downloading
python main.py --config config.yaml --dry-run

# Look for warnings in the output:
# - "Rate limiting detected"
# - "Requires browser automation"
# - "Connection error"
# - "Timeout accessing"
```

### Manual Verification

```bash
# Test URLs manually
curl -I "https://www.bd.gov.hk/en/resources/codes-and-references/codes-and-design-manuals/index.html"

# Check robots.txt
curl "https://www.bd.gov.hk/robots.txt"

# Test PDF download manually
wget "https://example.com/document.pdf"
```

## Getting Help

### Information to Provide

When seeking help, include:

1. **Command used**: Full command line with arguments
2. **Configuration**: Relevant parts of config.yaml
3. **Error message**: Complete error message and stack trace
4. **Environment**: OS, Python version, package versions
5. **Log output**: Relevant parts of log file with DEBUG level

### Useful Commands for Diagnostics

```bash
# System information
python --version
pip list
uname -a  # Linux/macOS
systeminfo  # Windows

# Network testing
ping www.bd.gov.hk
curl -I https://www.bd.gov.hk/
nslookup www.bd.gov.hk

# Disk space and permissions
df -h
ls -la downloads/
whoami
```

### Log Analysis

```bash
# Find errors in logs
grep -i error hk_pdf_crawler.log

# Find warnings
grep -i warning hk_pdf_crawler.log

# Find specific department issues
grep "Buildings Department" hk_pdf_crawler.log

# Find network issues
grep -i "timeout\|connection\|network" hk_pdf_crawler.log

# Find PDF detection issues
grep -i "pdf.*found\|no.*pdf" hk_pdf_crawler.log
```

## Prevention Tips

### Best Practices

1. **Always start with dry-run**: `--dry-run` flag identifies issues before downloading
2. **Use conservative settings initially**: Lower concurrency and higher delays
3. **Test with single departments**: Use `--departments` to test one at a time
4. **Monitor logs**: Keep an eye on log output for warnings
5. **Respect websites**: Don't overwhelm servers with too many concurrent requests
6. **Keep backups**: Use S3 or backup your downloads directory
7. **Update regularly**: Keep ChromeDriver and dependencies updated

### Monitoring During Crawling

```bash
# Monitor progress in real-time
tail -f hk_pdf_crawler.log

# Monitor system resources
top  # CPU and memory usage
df -h  # Disk space
netstat -i  # Network usage

# Monitor download directory
watch -n 5 'ls -la downloads/ | wc -l'  # Count files
watch -n 5 'du -sh downloads/'  # Directory size
```

This troubleshooting guide should help resolve most common issues. For persistent problems, enable debug logging and analyze the detailed output to identify the root cause.