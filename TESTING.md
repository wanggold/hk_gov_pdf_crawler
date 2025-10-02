# Testing Documentation for HK PDF Crawler

This document describes the comprehensive testing suite for the HK PDF Crawler project.

## Overview

The testing suite includes:
- **Unit Tests**: Core function testing with isolated components
- **Integration Tests**: Component interaction testing with mocked HTTP requests
- **End-to-End Tests**: Complete workflow testing with sample configurations
- **Error Handling Tests**: Network failures, invalid files, and edge cases
- **Browser Automation Tests**: JavaScript-heavy pages and interactive elements
- **S3 Integration Tests**: Cloud storage functionality with mocked AWS services

## Test Files

### Core Test Files

1. **`test_unit_core.py`** - Unit tests for core functions
   - Configuration loading and validation
   - PDF detection algorithms
   - URL discovery functionality
   - Utility functions
   - Data model validation

2. **`test_integration_mocked.py`** - Integration tests with mocked HTTP
   - Complete crawling workflow
   - Concurrent downloads
   - Rate limiting behavior
   - Invalid content handling

3. **`test_end_to_end.py`** - End-to-end workflow tests
   - YAML configuration workflow
   - Markdown configuration workflow
   - CLI interface testing
   - Report generation

4. **`test_error_handling.py`** - Error scenario testing
   - Network timeouts and failures
   - Invalid PDF content
   - File system errors
   - Retry mechanisms

5. **`test_browser_automation.py`** - Browser automation tests
   - Selenium WebDriver integration
   - JavaScript-heavy page handling
   - Interactive element clicking
   - Modal and form handling

6. **`test_s3_integration.py`** - S3 cloud storage tests
   - S3 configuration and initialization
   - File upload and download
   - Error handling and retries
   - Key generation and organization

### Existing Test Files

- `test_comprehensive.py` - Real-world scenario testing
- `test_integration.py` - FileDownloader integration
- `test_crawler_integration.py` - End-to-end crawler testing
- `test_concurrency.py` - Concurrent download testing
- `test_advanced_features.py` - Advanced feature testing
- `test_reporter.py` - Progress reporting testing

## Running Tests

### Quick Start

```bash
# Install dependencies and run all tests
python run_tests.py --install-deps
python run_tests.py

# Run quick test suite
python run_tests.py --quick

# Check test environment
python run_tests.py --check-env
```

### Individual Test Categories

```bash
# Unit tests only
python run_tests.py --unit

# Integration tests only
python run_tests.py --integration

# End-to-end tests only
python run_tests.py --e2e

# Error handling tests only
python run_tests.py --errors

# Browser automation tests only
python run_tests.py --browser

# S3 integration tests only
python run_tests.py --s3
```

### Coverage Reports

```bash
# Generate coverage report
python run_tests.py --coverage

# View HTML coverage report
open htmlcov/index.html
```

### Manual Test Execution

```bash
# Run specific test file
pytest test_unit_core.py -v

# Run specific test class
pytest test_unit_core.py::TestConfigurationLoading -v

# Run specific test method
pytest test_unit_core.py::TestConfigurationLoading::test_load_valid_yaml_config -v

# Run with coverage
pytest --cov=. --cov-report=html test_unit_core.py
```

## Test Dependencies

The testing suite requires the following additional packages:

```
pytest>=7.0.0              # Testing framework
pytest-cov>=4.0.0          # Coverage reporting
responses>=0.23.0           # HTTP request mocking
moto>=4.2.0                # AWS service mocking
```

These are automatically installed when running `python run_tests.py --install-deps`.

## Test Structure and Patterns

### Unit Test Structure

```python
class TestComponentName:
    """Test description"""
    
    def setup_method(self):
        """Set up test fixtures"""
        pass
    
    def teardown_method(self):
        """Clean up after tests"""
        pass
    
    def test_specific_functionality(self):
        """Test specific functionality"""
        # Arrange
        # Act
        # Assert
        pass
```

### Mocking Patterns

#### HTTP Request Mocking

```python
import responses

@responses.activate
def test_http_request():
    responses.add(
        responses.GET,
        'https://example.com/test.pdf',
        body=b'PDF content',
        status=200,
        content_type='application/pdf'
    )
    # Test code here
```

#### AWS Service Mocking

```python
from unittest.mock import patch

@patch('downloader.boto3.client')
def test_s3_upload(mock_boto3_client):
    mock_s3_client = Mock()
    mock_boto3_client.return_value = mock_s3_client
    # Test code here
```

#### Browser Automation Mocking

```python
@patch('browser.webdriver.Chrome')
def test_browser_functionality(mock_chrome):
    mock_driver = Mock()
    mock_chrome.return_value = mock_driver
    # Test code here
```

## Test Coverage Goals

The testing suite aims for:
- **90%+ code coverage** for core modules
- **100% coverage** for critical functions (PDF detection, file validation)
- **Comprehensive error scenario coverage**
- **Integration testing** for all major workflows

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    - name: Run tests
      run: python run_tests.py
```

## Test Data and Fixtures

### Sample Configuration Files

Tests use temporary configuration files created during test execution:

```yaml
departments:
  test_dept:
    name: 'Test Department'
    seed_urls: ['https://example.com']
    max_depth: 2
    max_pages: 10
settings:
  delay_between_requests: 0.1
  max_concurrent_downloads: 2
storage:
  local_path: './test_downloads'
  s3_enabled: false
```

### Mock PDF Content

```python
pdf_content = b'%PDF-1.4\n' + b'Mock PDF content. ' * 100 + b'\n%%EOF'
```

### Mock HTML Pages

```html
<html>
<body>
    <h1>Test Department</h1>
    <a href="document1.pdf">Annual Report PDF</a>
    <a href="manual.pdf">User Manual</a>
</body>
</html>
```

## Performance Testing

### Load Testing

```python
def test_concurrent_download_performance():
    """Test performance with multiple concurrent downloads"""
    urls = [f'https://example.com/doc{i}.pdf' for i in range(50)]
    # Test concurrent download performance
```

### Memory Usage Testing

```python
def test_memory_usage():
    """Test memory usage during large file processing"""
    # Monitor memory usage during PDF processing
```

## Browser Testing Requirements

### Chrome WebDriver Setup

For browser automation tests, Chrome WebDriver is required:

```bash
# Install Chrome (Ubuntu/Debian)
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
sudo sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
sudo apt-get update
sudo apt-get install google-chrome-stable

# Install ChromeDriver
pip install webdriver-manager
```

### Headless Testing

All browser tests run in headless mode by default for CI/CD compatibility:

```python
handler = BrowserHandler(headless=True)
```

## Troubleshooting Tests

### Common Issues

1. **Import Errors**: Ensure all dependencies are installed
   ```bash
   python run_tests.py --install-deps
   ```

2. **Browser Tests Failing**: Install Chrome and ChromeDriver
   ```bash
   pip install webdriver-manager
   ```

3. **Permission Errors**: Ensure test directories are writable
   ```bash
   chmod 755 test_temp_dir
   ```

4. **Network-Related Test Failures**: Check internet connectivity for integration tests

### Debug Mode

Run tests with verbose output and stop on first failure:

```bash
pytest -v -x --tb=long test_unit_core.py
```

### Test Isolation

Each test method uses temporary directories and mocked services to ensure isolation:

```python
def setup_method(self):
    self.temp_dir = tempfile.mkdtemp()

def teardown_method(self):
    shutil.rmtree(self.temp_dir, ignore_errors=True)
```

## Contributing to Tests

### Adding New Tests

1. **Choose appropriate test file** based on functionality
2. **Follow naming conventions**: `test_functionality_description`
3. **Use proper fixtures** for setup and teardown
4. **Mock external dependencies** (HTTP, AWS, browser)
5. **Include both positive and negative test cases**
6. **Add docstrings** explaining test purpose

### Test Review Checklist

- [ ] Tests are isolated and don't depend on external services
- [ ] Both success and failure scenarios are covered
- [ ] Mocking is used appropriately for external dependencies
- [ ] Test names clearly describe what is being tested
- [ ] Temporary files and resources are properly cleaned up
- [ ] Tests run quickly (< 1 second per test for unit tests)
- [ ] Coverage is maintained or improved

## Test Results and Reporting

### Console Output

```
================================ test session starts ================================
collected 156 items

test_unit_core.py::TestConfigurationLoading::test_load_valid_yaml_config PASSED
test_unit_core.py::TestConfigurationLoading::test_load_config_missing_file PASSED
...

============================== 156 passed in 45.23s ==============================
```

### Coverage Report

```
Name                    Stmts   Miss  Cover   Missing
-----------------------------------------------------
config.py                 145      8    94%   23-25, 89-91
discovery.py              234     12    95%   156-158, 201-205
downloader.py             198      5    97%   45-47
browser.py                167     23    86%   78-82, 134-145
crawler.py                189      7    96%   234-237
models.py                  45      0   100%
utils.py                   89      4    95%   67-69, 123
-----------------------------------------------------
TOTAL                    1067     59    94%
```

### HTML Coverage Report

The HTML coverage report provides detailed line-by-line coverage information:
- Open `htmlcov/index.html` in a browser
- Click on individual files to see uncovered lines
- Use to identify areas needing additional tests

This comprehensive testing suite ensures the HK PDF Crawler is robust, reliable, and maintainable.